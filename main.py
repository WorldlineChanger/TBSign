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
# 2. 获取关注的贴吧
# -----------------------------
def get_favorite(bduss):
    """获取用户关注的贴吧列表，包含分页和嵌套 flatten"""
    logger.info("获取关注的贴吧开始")
    returnData = {}
    i = 1
    data = {
        'BDUSS': bduss,
        '_client_type': '2',
        '_client_id': 'wappc_1534235498291_488',
        '_client_version': '9.7.8.0',
        '_phone_imei': '000000000000000',
        'from': '1008621y',
        'page_no': '1',
        'page_size': '200',
        'model': 'MI+5',
        'net_type': '1',
        'timestamp': str(int(time.time())),
        'vcode_tag': '11',
    }
    data = encodeData(data)
    try:
        resp = s.post(url=LIKIE_URL, data=data, timeout=10)
        resp.raise_for_status()
        res = resp.json()
    except Exception as e:
        logger.error("获取关注的贴吧出错: %s", e)
        return []
    returnData = res
    if 'forum_list' not in returnData:
        returnData['forum_list'] = []
    if res['forum_list'] == []:
        returnData['forum_list'] = {'gconforum': [], 'non-gconforum': []}
    else:
        returnData['forum_list'].setdefault('non-gconforum', [])
        returnData['forum_list'].setdefault('gconforum', [])
    while 'has_more' in res and res['has_more'] == '1':
        i += 1
        data = {
            'BDUSS': bduss,
            '_client_type': '2',
            '_client_id': 'wappc_1534235498291_488',
            '_client_version': '9.7.8.0',
            '_phone_imei': '000000000000000',
            'from': '1008621y',
            'page_no': str(i),
            'page_size': '200',
            'model': 'MI+5',
            'net_type': '1',
            'timestamp': str(int(time.time())),
            'vcode_tag': '11',
        }
        data = encodeData(data)
        try:
            resp = s.post(url=LIKIE_URL, data=data, timeout=10)
            resp.raise_for_status()
            res = resp.json()
        except Exception as e:
            logger.error("获取关注的贴吧出错: %s", e)
            continue
        flist = res.get('forum_list', {})
        if 'non-gconforum' in flist:
            returnData['forum_list']['non-gconforum'].append(flist['non-gconforum'])
        if 'gconforum' in flist:
            returnData['forum_list']['gconforum'].append(flist['gconforum'])
    # flatten 嵌套列表
    t = []
    for section in ('non-gconforum', 'gconforum'):
        for item in returnData['forum_list'][section]:
            if isinstance(item, list):
                for j in item:
                    if isinstance(j, list):
                        for k in j:
                            t.append(k)
                    else:
                        t.append(j)
            else:
                t.append(item)
    logger.info("获取关注的贴吧结束，共 %d 个", len(t))
    return t

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
    try:
        fid = get_fid_by_name(bduss, bar_name)
    except Exception as e:
        logger.error(f"获取 fid 失败: {e}")
        return success
    cookies = {BDUSS: bduss}
    def rnd_sleep(): time.sleep(random.uniform(3, 8))
    if DO_MODERATOR_POST:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        content = f"{current_time} #(滑稽)"
        reply_data = {'BDUSS': bduss, 'content': content, 'fid': fid, 'tid': post_id, 'vcode_tag': '11', 'tbs': tbs}
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
    if DO_MODERATOR_TOP:
        rnd_sleep()
        s.get(SET_TOP_URL, headers=get_headers(is_mobile=True), cookies=cookies, params={'tn':'bdTOP','z':post_id,'tbs':tbs,'word':bar_name})
        success['top'] = True
        logger.info(f"置顶尝试完成: {post_id}")
        rnd_sleep()
        s.get(SET_TOP_URL, headers=get_headers(is_mobile=True), cookies=cookies, params={'tn':'bdUNTOP','z':post_id,'tbs':tbs,'word':bar_name})
        logger.info(f"取消置顶尝试完成: {post_id}")
    return success

# -----------------------------
# 5. 邮件汇报函数（恢复原始样式）
# -----------------------------
def send_email(sign_list, total_sign_time, task_status):
    moderated_bars = ENV.get('MODERATED_BARS', '').split(',') if 'MODERATED_BARS' in ENV else []
    if ('HOST' not in ENV or 'FROM' not in ENV or 'TO' not in ENV or 'AUTH' not in ENV):
        logger.error("未配置邮箱")
        return
    HOST = ENV['HOST']
    FROM = ENV['FROM']
    TO = ENV['TO'].split('#')
    AUTH = ENV['AUTH']
    length = len(sign_list)
    subject = f"{time.strftime('%Y-%m-%d')} 签到{length}个贴吧账号"
    body = f"<h2 style='color: #66ccff;'>签到报告 - {time.strftime('%Y年%m月%d日')}</h2>"
    body += f"<h3>共有{length}个账号签到，总签到时间：{format_time(total_sign_time)}</h3>"
    if moderated_bars:
        body += "<h3>吧主考核任务执行情况：</h3>"
        for bar_name, status in zip(moderated_bars, task_status):
            icon = "✅" if status['reply'] or status['top'] else "❌"
            body += f"""<div class="child">
                {bar_name}：{icon}<br>
                发帖操作：{"成功" if status['reply'] else "失败"}<br>
                置顶操作：{"成功" if status['top'] else "失败"}
            </div>"""
    body += """
    <style>
    .child {
      background-color: rgba(173, 216, 230, 0.19);
      padding: 10px;
    }

    .child * {
      margin: 5px;
    }
    </style>
    """
    for idx, user_favorites in enumerate(sign_list):
        body += f"<br><b>账号{idx+1}的签到信息：</b><br><br>"
        for i in user_favorites:
            body += f"""<div class="child">
                <div class="name"> 贴吧名称: {i['name']} </div>
                <div class="slogan"> 贴吧简介: {i.get('slogan','无')} </div>
            </div>
            <hr>"""
    try:
        msg = MIMEText(body, 'html', 'utf-8')
        msg['subject'] = subject
        smtp = smtplib.SMTP()
        smtp.connect(HOST)
        smtp.login(FROM, AUTH)
        smtp.sendmail(FROM, TO, msg.as_string())
        smtp.quit()
        logger.info("邮件发送成功")
    except smtplib.SMTPException as e:
        logger.error("邮件发送失败：%s", e)
    except Exception as e:
        logger.error("邮件发送时发生错误：%s", e)

# -----------------------------
# 工具函数: 时间格式化
# -----------------------------
def format_time(seconds):
    minutes = seconds // 60
    remaining = seconds % 60
    if minutes > 0:
        return f"{minutes}分{remaining}秒"
    else:
        return f"{remaining}秒"

# -----------------------------
# 根据吧名获取 fid
# -----------------------------
def get_fid_by_name(bduss, kw):
    """
    根据吧名获取 fid：
      1. 去掉末尾的“吧”字
      2. 调用分享接口并解析 JSON 返回的 data.fid
    """
    name = kw.rstrip("吧")
    url = (
        "http://tieba.baidu.com/f/commit/share/fnameShareApi"
        f"?ie=utf-8&fname={quote(name)}"
    )
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
        logger.error(f"获取吧名 {kw!r} 的 fid 失败：%s", e)
        raise

# -----------------------------
# 主入口
# -----------------------------
def main():
    """
    主函数：签到所有账号，条件触发吧主任务后进行回复/置顶
    """
    if 'BDUSS' not in ENV:
        logger.error("未配置 BDUSS，停止执行")
        return

    # 新增：吧主任务执行间隔
    interval_days = int(ENV.get('MODERATOR_INTERVAL_DAYS', '3'))
    from pathlib import Path
    import json
    last_file = Path('last_moderator_run.json')
    today_str = time.strftime('%Y-%m-%d')
    can_run_moderator = True
    if last_file.exists():
        try:
            data = json.loads(last_file.read_text())
            last_str = data.get('last_run', '')
            last_time = time.strptime(last_str, '%Y-%m-%d')
            last_ts = time.mktime(last_time)
            diff_days = (time.time() - last_ts) / 86400
            if diff_days < interval_days:
                can_run_moderator = False
                logger.info(f"吧主任务距离上次运行仅 {diff_days:.1f} 天，需间隔 {interval_days} 天，跳过吧主任务")
        except Exception as e:
            logger.warning(f"读取上次运行时间失败: {e}")

    bds_list = ENV['BDUSS'].split('#')
    all_favorites = []
    total_sign_time = 0
    task_status = []
    for idx, bduss in enumerate(bds_list, start=1):
        logger.info(f"开始第{idx}个用户签到")
        start_time = time.time()
        try:
            tbs = get_tbs(bduss)
        except Exception:
            continue
        favorites = get_favorite(bduss)
        logger.info("账号%d关注贴吧数量: %d", idx, len(favorites))
        all_favorites.append(favorites)
        for f in favorites:
            time.sleep(random.uniform(1, 3))
            client_sign(bduss, tbs, f['id'], f['name'])
        total_sign_time += int(time.time() - start_time)
        if can_run_moderator and str(idx-1) == MODERATOR_BDUSS_INDEX and MODERATED_BARS and TARGET_POST_IDS:
            bars = [b.strip() for b in MODERATED_BARS.split(',') if b.strip()]
            posts = [p.strip() for p in TARGET_POST_IDS.split(',') if p.strip()]
            seen = set()
            for bar, pid in zip(bars, posts):
                if bar in seen: continue
                seen.add(bar)
                logger.info(f"执行吧主任务:{bar}")
                status = moderator_task(bduss, tbs, bar, pid)
                task_status.append(status)
                time.sleep(5)
    if can_run_moderator and task_status:
        try:
            import json
            Path('last_moderator_run.json').write_text(json.dumps({'last_run': today_str}))
            logger.info(f"更新吧主任务上次运行时间: {today_str}")
        except Exception as e:
            logger.warning(f"更新 last_run 失败: {e}")
    send_email(all_favorites, total_sign_time, task_status)
    logger.info("所有用户签到结束")

if __name__ == '__main__':
    main()
