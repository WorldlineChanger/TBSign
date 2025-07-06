# -*- coding:utf-8 -*-

import os
import requests
import hashlib
import time
import copy
import logging
import random
import smtplib
from email.mime.text import MIMEText
from urllib.parse import quote
from json import JSONDecodeError

# -----------------------------
# 日志配置
# -----------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -----------------------------
# User-Agent 随机轮换设置
# -----------------------------
USER_AGENTS_DESKTOP = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
]
MOBILE_UA = (
    'Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36'
)

def get_headers(is_mobile=False):
    """获取基础请求头，随机 User-Agent"""
    ua = MOBILE_UA if is_mobile else random.choice(USER_AGENTS_DESKTOP)
    return {
        'Host': 'tieba.baidu.com',
        'User-Agent': ua,
    }

# -----------------------------
# API 地址
# -----------------------------
REPLY_URL   = "https://tieba.baidu.com/f/commit/post/add"        # 回帖接口
DELETE_URL  = "https://c.tieba.baidu.com/c/u/comment/postDel"    # 删除回复接口
SET_TOP_URL = "https://tieba.baidu.com/mo/q"                     # 置顶/取消置顶接口
TBS_URL     = "http://tieba.baidu.com/dc/common/tbs"             # 获取 tbs
LIKIE_URL   = "http://c.tieba.baidu.com/c/f/forum/like"          # 获取关注贴吧接口
SIGN_URL    = "http://c.tieba.baidu.com/c/c/forum/sign"          # 签到接口

# -----------------------------
# 环境变量 & 开关
# -----------------------------
ENV                     = os.environ
DO_MODERATOR_TASK       = ENV.get('MODERATOR_TASK_ENABLE', 'false').lower() == 'false'
DO_MODERATOR_POST       = ENV.get('MODERATOR_POST_ENABLE',  'false').lower() == 'true'
DO_MODERATOR_TOP        = ENV.get('MODERATOR_TOP_ENABLE',   'false').lower() == 'true'
MODERATOR_BDUSS_INDEX   = ENV.get('MODERATOR_BDUSS_INDEX', '0')
MODERATED_BARS          = ENV.get('MODERATED_BARS', '')
TARGET_POST_IDS         = ENV.get('TARGET_POST_IDS', '')

# -----------------------------
# 请求签名 & 常量
# -----------------------------
COOKIE       = "Cookie"
BDUSS        = "BDUSS"
SIGN_KEY     = 'tiebaclient!!!'
UTF8         = "utf-8"
SIGN_DATA    = {
    '_client_type': '2',
    '_client_version': '9.7.8.0',
    '_phone_imei': '000000000000000',
    'model': 'MI+5',
    'net_type': '1',
}

# 全局 Session
s = requests.Session()

# -----------------------------
# 风控检测函数
# -----------------------------
def check_wind_control(resp_json):
    """
    检测是否触发风控，根据常见 error_code 暂停。
    返回 True 表示触发风控并已退避。
    """
    ec = resp_json.get('error_code')
    if ec in (110, 221023, 219016):
        logger.warning(f"触发风控({ec})，暂停5分钟")
        time.sleep(300)
        return True
    return False

# -----------------------------
# 请求参数签名
# -----------------------------
def encodeData(data):
    """
    对请求参数进行签名，按照 key 排序后拼接 SIGN_KEY MD5
    """
    items = sorted(data.items())
    s_str = ''.join(f"{k}={v}" for k, v in items)
    sign = hashlib.md5((s_str + SIGN_KEY).encode(UTF8)).hexdigest().upper()
    data['sign'] = sign
    return data

# -----------------------------
# 1. 获取 tbs
# -----------------------------
def get_tbs(bduss):
    """获取图形验证码 tbs，用于各种签名接口"""
    logger.info("获取 tbs 开始")
    headers = get_headers()
    headers.update({COOKIE: f"{BDUSS}={bduss}"})
    for attempt in range(3):
        try:
            resp = s.get(TBS_URL, headers=headers, timeout=5)
            resp.raise_for_status()
            tbs = resp.json().get('tbs')
            logger.info(f"获取 tbs 完成: {tbs}")
            return tbs
        except Exception as e:
            logger.warning(f"获取 tbs 第{attempt+1}次失败: {e}")
            time.sleep(2)
    logger.error("获取 tbs 失败，签到中止")
    raise RuntimeError("TBS 获取失败")

# -----------------------------
# 2. 获取关注的贴吧（分页+flatten）
# -----------------------------
def get_favorite(bduss):
    """获取用户关注的贴吧列表，包含分页和嵌套 flatten"""
    logger.info("获取关注的贴吧开始")
    returnData = {}
    page = 1
    # 初始请求
    data = {
        'BDUSS': bduss,
        '_client_type': '2', '_client_id': 'wappc_1534235498291_488',
        '_client_version': '9.7.8.0', '_phone_imei': '000000000000000',
        'from': '1008621y', 'page_no': str(page), 'page_size': '200',
        'model': 'MI+5', 'net_type': '1',
        'timestamp': str(int(time.time())), 'vcode_tag': '11',
    }
    resp = s.post(LIKIE_URL, headers=get_headers(), data=encodeData(data), timeout=10)
    try:
        res = resp.json()
    except Exception as e:
        logger.error(f"获取关注的贴吧出错: {e}")
        return []
    returnData = res
    returnData.setdefault('forum_list', {})
    fl = returnData['forum_list'] or {}
    fl.setdefault('non-gconforum', [])
    fl.setdefault('gconforum', [])
    # 分页
    while res.get('has_more') == '1':
        page += 1
        data['page_no'] = str(page)
        data['timestamp'] = str(int(time.time()))
        resp = s.post(LIKIE_URL, headers=get_headers(), data=encodeData(data), timeout=10)
        try:
            res = resp.json()
            fl2 = res.get('forum_list', {})
            if 'non-gconforum' in fl2:
                fl['non-gconforum'].append(fl2['non-gconforum'])
            if 'gconforum' in fl2:
                fl['gconforum'].append(fl2['gconforum'])
        except Exception:
            break
    # flatten 列表
    flat = []
    for section in ('non-gconforum', 'gconforum'):
        for item in fl[section]:
            if isinstance(item, list):
                for sub in item:
                    if isinstance(sub, list):
                        flat.extend(sub)
                    else:
                        flat.append(sub)
            else:
                flat.append(item)
    logger.info(f"获取关注的贴吧结束，共 {len(flat)} 个")
    return flat

# -----------------------------
# 3. 客户端签到
# -----------------------------
def client_sign(bduss, tbs, fid, kw):
    """执行签到操作"""
    logger.info(f"签到贴吧: {kw}")
    data = {**SIGN_DATA, 'BDUSS': bduss, 'fid': fid, 'kw': kw, 'tbs': tbs, 'timestamp': str(int(time.time()))}
    resp = s.post(SIGN_URL, headers=get_headers(), cookies={BDUSS: bduss}, data=encodeData(data), timeout=10)
    try:
        jr = resp.json()
        if check_wind_control(jr):
            return jr
        return jr
    except JSONDecodeError:
        return {'error_code': 0}

# -----------------------------
# 4. 吧主任务：回复+删除 & 置顶/取消置顶
# -----------------------------
def moderator_task(bduss, tbs, bar_name, post_id):
    """执行吧主考核任务，返回 {'reply': bool, 'top': bool}"""
    success = {'reply': False, 'top': False}
    if not DO_MODERATOR_TASK:
        return success
    # 获取 fid
    try:
        fid = get_fid_by_name(bduss, bar_name)
    except Exception as e:
        logger.error(f"获取 fid 失败: {e}")
        return success
    cookies = {BDUSS: bduss}
    # 随机延时
    def rnd_sleep(): time.sleep(random.uniform(3, 8))
    # 回复 & 删除
    if DO_MODERATOR_POST:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        content = f"{current_time} #(滑稽)"
        reply_data = {'BDUSS': bduss, 'content': content, 'fid': fid, 'tid': post_id, 'vcode_tag': '11', 'tbs': tbs}
        # 增加埋点字段
        reply_data['mouse_pwd_t'] = str(int(time.time() * 1000))
        reply_data['mouse_pwd']   = reply_data['mouse_pwd_t']
        rnd_sleep()
        resp = s.post(REPLY_URL, headers=get_headers(is_mobile=True), cookies=cookies, data=encodeData(reply_data), timeout=10)
        try:
            jr = resp.json()
            if check_wind_control(jr): return success
            if jr.get('error_code') == 0:
                success['reply'] = True
                pid = jr.get('data', {}).get('post_id') or jr.get('pid')
                logger.info(f"回复成功 pid={pid}")
                if pid:
                    rnd_sleep()
                    del_data = {'post_id': pid, 'del_type': '0', 'tbs': tbs}
                    del_resp = s.post(DELETE_URL, headers=get_headers(is_mobile=True), cookies=cookies, data=encodeData(del_data), timeout=10)
                    logger.info(f"删除回复 status={del_resp.status_code}")
        except Exception as e:
            logger.error(f"回复/删除阶段失败: {e}")
    # 置顶 & 取消置顶
    if DO_MODERATOR_TOP:
        rnd_sleep()
        # 置顶
        s.get(SET_TOP_URL, headers=get_headers(is_mobile=True), cookies=cookies, params={'tn':'bdTOP','z':post_id,'tbs':tbs,'word':bar_name})
        success['top'] = True
        logger.info(f"置顶尝试完成: {post_id}")
        rnd_sleep()
        # 取消置顶
        s.get(SET_TOP_URL, headers=get_headers(is_mobile=True), cookies=cookies, params={'tn':'bdUNTOP','z':post_id,'tbs':tbs,'word':bar_name})
        logger.info(f"取消置顶尝试完成: {post_id}")
    return success

# -----------------------------
# 5. 邮件汇报 & 主函数
# -----------------------------
def format_time(seconds):
    minutes = seconds // 60
    sec = seconds % 60
    return f"{minutes}分{sec}秒" if minutes else f"{sec}秒"

def send_email(sign_list, total_sign_time, task_status):
    moderated_bars = [b.strip() for b in MODERATED_BARS.split(',') if b.strip()]
    HOST = ENV.get('HOST')
    FROM = ENV.get('FROM')
    TO   = ENV.get('TO','').split('#')
    AUTH = ENV.get('AUTH')
    if not all([HOST, FROM, TO, AUTH]):
        logger.error("邮件参数未配置完整，跳过发送")
        return
    subject = f"{time.strftime('%Y-%m-%d')} 签到{len(sign_list)}个账号报告"
    body = f"<h2>签到报告 - {time.strftime('%Y年%m月%d日')}</h2>"
    body += f"<p>共 {len(sign_list)} 个账号签到，耗时 {format_time(total_sign_time)}</p>"
    if moderated_bars:
        body += "<h3>吧主考核任务：</h3>"
        for bar, st in zip(moderated_bars, task_status):
            icon='✅' if st['reply'] or st['top'] else '❌'
            body += f"<p>{bar}：{icon} (发帖:{'✓' if st['reply'] else '✗'},置顶:{'✓' if st['top'] else '✗'})</p>"
    for idx, favs in enumerate(sign_list,1):
        body += f"<h4>账号{idx}关注贴吧：</h4>"
        for f in favs:
            body += f"<p>吧名:{f.get('name')}，简介:{f.get('slogan','无')}</p>"
    msg = MIMEText(body,'html','utf-8')
    msg['Subject']=subject
    try:
        smtp = smtplib.SMTP(HOST)
        smtp.login(FROM,AUTH)
        smtp.sendmail(FROM,TO,msg.as_string())
        smtp.quit()
        logger.info("邮件发送成功")
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")

def get_fid_by_name(bduss, kw):
    """
    根据吧名获取 fid：
      1. 去掉末尾的“吧”字
      2. 调用分享接口并解析 JSON 返回的 data.fid
    """
    # 1. 去掉“吧”后缀，防止接口对带“吧”的名称返回空
    name = kw.rstrip("吧")

    # 2. 构造分享接口并对名称进行 percent-encoding
    url = (
        "http://tieba.baidu.com/f/commit/share/fnameShareApi"
        f"?ie=utf-8&fname={quote(name)}"
    )

    # 使用随机 UA
    headers = get_headers()
    headers.update({COOKIE: f"{BDUSS}={bduss}"})
    try:
        resp = s.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json().get('data', {})
        fid = data.get('fid')
        if not fid:
            raise ValueError(f"接口返回 data 中缺少 fid：{data}")
        return str(fid)
    except Exception as e:
        logger.error(f"获取吧名 {kw!r} 的 fid 失败：{e}")
        raise

def main():
    if 'BDUSS' not in ENV:
        logger.error("未配置 BDUSS，停止执行")
        return
    bds=ENV['BDUSS'].split('#')
    all_fav=[]
    tot_time=0
    task_status=[]
    for idx,bduss in enumerate(bds,1):
        logger.info(f"开始账号{idx}签到")
        st=time.time()
        try: tbs=get_tbs(bduss)
        except: continue
        favs=get_favorite(bduss)
        all_fav.append(favs)
        for f in favs:
            time.sleep(random.uniform(1,3))
            client_sign(bduss,tbs,f['id'],f['name'])
        tot_time+=int(time.time()-st)
        if str(idx-1)==MODERATOR_BDUSS_INDEX and MODERATED_BARS and TARGET_POST_IDS:
            bars=[b.strip() for b in MODERATED_BARS.split(',') if b.strip()]
            posts=[p.strip() for p in TARGET_POST_IDS.split(',') if p.strip()]
            seen=set()
            for bar,pid in zip(bars,posts):
                if bar in seen: continue
                seen.add(bar)
                logger.info(f"执行吧主任务:{bar}")
                st=moderator_task(bduss,tbs,bar,pid)
                task_status.append(st)
                time.sleep(5)
    send_email(all_fav,tot_time,task_status)
    logger.info("脚本执行完毕")

if __name__=='__main__':
    main()
