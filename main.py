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


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API_URL
LIKIE_URL = "http://c.tieba.baidu.com/c/f/forum/like"
TBS_URL = "http://tieba.baidu.com/dc/common/tbs"
SIGN_URL = "http://c.tieba.baidu.com/c/c/forum/sign"
REPLY_URL = "http://c.tieba.baidu.com/c/c/post/add"
DELETE_URL = "http://c.tieba.baidu.com/c/c/post/delete"
SET_TOP_URL = "http://c.tieba.baidu.com/c/c/bawu/setTopThread"

ENV = os.environ

HEADERS = {
    'Host': 'tieba.baidu.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
}
SIGN_DATA = {
    '_client_type': '2',
    '_client_version': '9.7.8.0',
    '_phone_imei': '000000000000000',
    'model': 'MI+5',
    "net_type": "1",
}

# VARIABLE NAME
COOKIE = "Cookie"
BDUSS = "BDUSS"
EQUAL = r'='
EMPTY_STR = r''
TBS = 'tbs'
PAGE_NO = 'page_no'
ONE = '1'
TIMESTAMP = "timestamp"
DATA = 'data'
FID = 'fid'
SIGN_KEY = 'tiebaclient!!!'
UTF8 = "utf-8"
SIGN = "sign"
KW = "kw"

s = requests.Session()


# def get_tbs(bduss):
#     logger.info("获取tbs开始")
#     headers = copy.copy(HEADERS)
#     headers.update({COOKIE: EMPTY_STR.join([BDUSS, EQUAL, bduss])})
#     try:
#         tbs = s.get(url=TBS_URL, headers=headers, timeout=5).json()[TBS]
#     except Exception as e:
#         logger.error("获取tbs出错" + str(e))
#         logger.info("重新获取tbs开始")
#         tbs = s.get(url=TBS_URL, headers=headers, timeout=5).json()[TBS]
#     logger.info("获取tbs结束")
#     return tbs

def get_tbs(bduss):
    logger.info("获取tbs开始")
    headers = copy.copy(HEADERS)
    headers.update({COOKIE: EMPTY_STR.join([BDUSS, EQUAL, bduss])})
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = s.get(url=TBS_URL, headers=headers, timeout=5)
            response.raise_for_status()
            tbs = response.json()[TBS]
            logger.info("获取tbs结束")
            return tbs
        except (requests.exceptions.RequestException, KeyError) as e:
            logger.warning(f"获取tbs第 {attempt + 1} 次失败，原因: {str(e)}")
            if attempt == max_retries - 1:
                logger.error("获取tbs失败，签到中止")
                raise  # 抛出异常让外层处理
            time.sleep(2)

def get_favorite(bduss):
    logger.info("获取关注的贴吧开始")
    # 客户端关注的贴吧
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
        return {'gconforum': [], 'non-gconforum': []}
    if 'non-gconforum' not in returnData['forum_list']:
        returnData['forum_list']['non-gconforum'] = []
    if 'gconforum' not in returnData['forum_list']:
        returnData['forum_list']['gconforum'] = []
    while 'has_more' in res and res['has_more'] == '1':
        i = i + 1
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
        if 'forum_list' not in res:
            continue
        if 'non-gconforum' in res['forum_list']:
            returnData['forum_list']['non-gconforum'].append(res['forum_list']['non-gconforum'])
        if 'gconforum' in res['forum_list']:
            returnData['forum_list']['gconforum'].append(res['forum_list']['gconforum'])

    t = []
    for i in returnData['forum_list']['non-gconforum']:
        if isinstance(i, list):
            for j in i:
                if isinstance(j, list):
                    for k in j:
                        t.append(k)
                else:
                    t.append(j)
        else:
            t.append(i)
    for i in returnData['forum_list']['gconforum']:
        if isinstance(i, list):
            for j in i:
                if isinstance(j, list):
                    for k in j:
                        t.append(k)
                else:
                    t.append(j)
        else:
            t.append(i)
    logger.info("获取关注的贴吧结束")
    return t


def encodeData(data):
    s = EMPTY_STR
    keys = data.keys()
    for i in sorted(keys):
        s += i + EQUAL + str(data[i])
    sign = hashlib.md5((s + SIGN_KEY).encode(UTF8)).hexdigest().upper()
    data.update({SIGN: str(sign)})
    return data


def get_fid_by_name(bduss: str, kw: str) -> str:
    """
    根据吧名获取 fid：
      1. 去掉末尾的“吧”字
      2. 调用分享接口并解析 JSON 返回的 data.fid
    """
    
    # 1. 去掉“吧”后缀
    name = kw.rstrip("吧")  # 防止接口对带“吧”的名称返回空

    # 2. 构造接口并对 name 做 percent-encoding
    url = (
        "http://tieba.baidu.com/f/commit/share/fnameShareApi"
        f"?ie=utf-8&fname={quote(name)}"
    )

    # 3. 发起请求 提取 fid
    headers = {
        'Host': 'tieba.baidu.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
        'Cookie': f"BDUSS={bduss}"
    }
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

def client_sign(bduss, tbs, fid, kw):
    # 客户端签到
    logger.info("开始签到贴吧：" + kw)
    data = copy.copy(SIGN_DATA)
    data.update({BDUSS: bduss, FID: fid, KW: kw, TBS: tbs, TIMESTAMP: str(int(time.time()))})
    data = encodeData(data)
    
    max_retries = 3  # 最大重试次数
    retry_delay = 5  # 重试间隔（秒）
    
    for attempt in range(max_retries):
        try:
            response = s.post(url=SIGN_URL, data=data, timeout=10)
            response.raise_for_status()  # 检查HTTP状态码
            res = response.json()  # 解析JSON
            return res
        except (requests.exceptions.Timeout, requests.exceptions.HTTPError, requests.exceptions.JSONDecodeError) as e:
            logger.warning(f"签到贴吧 {kw} 第 {attempt + 1} 次失败，原因: {str(e)}")
            if attempt == max_retries - 1:
                logger.error(f"贴吧 {kw} 签到失败，已达最大重试次数")
                return {"error": "Max retries exceeded"}
            time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"贴吧 {kw} 签到发生未知错误: {str(e)}")
            return {"error": "Unexpected error"}
    
    return {"error": "Unknown error"}


def moderator_task(bduss, tbs, bar_name, post_id):
    """执行吧主考核任务"""
    success_flag = {'reply': False, 'top': False}

    cookies = { 'BDUSS': bduss }
    headers = copy.copy(HEADERS)

    try:
        fid = get_fid_by_name(bduss, bar_name)
    except Exception as e:
        logger.error("获取 fid 失败，跳过吧主任务：%s", e)
        return success_flag

    # 1. 回复并删除
    reply_data = {
        'BDUSS': bduss,
        'content': '#(滑稽)',
        'fid': fid,
        'tid': post_id,
        'vcode_tag': '11',
        'tbs': tbs
    }
    try:
        # 发帖
        resp = s.post(REPLY_URL,
                      data=encodeData(reply_data),
                      headers=headers,
                      cookies=cookies,
                      timeout=10)
        resp.raise_for_status()
        jr = resp.json()
    
        if str(jr.get('error_code', '')) == '0':
            success_flag['reply'] = True
        
            # 先从嵌套 data 取，再从顶层 pid 取
            pid = jr.get('data', {}).get('post_id') or jr.get('pid')
            logger.info("回复成功，post_id=%s", pid)

            # 删除
            if pid:
                time.sleep(3)
                delete_data = {
                    'BDUSS': bduss,
                    'post_id': pid,
                    'tbs': tbs
                }
                # 通过 cookies 递交 BDUSS，并优雅处理空响应
                del_resp = s.post(DELETE_URL,
                                  data=encodeData(delete_data),
                                  headers=headers,
                                  cookies=cookies,
                                  timeout=10)
                logger.info("删除响应 status=%s", del_resp.status_code)
                del_resp.raise_for_status()
                try:
                    dj = del_resp.json()
                    if dj.get('error_code') != '0':
                        logger.error("删除操作返回非0：%r", dj)
                    else:
                        logger.info("删除成功，pid=%s", pid)
                except JSONDecodeError:
                    logger.info("删除接口无 JSON 返回，视为成功，pid=%s", pid)
            else:
                logger.error("回复成功却未返回 post_id/pid：%r", jr)
        else:
            logger.error("回复操作失败，接口返回：%r", jr)

    except requests.exceptions.RequestException as e:
        logger.error("HTTP 异常，回复/删除阶段：%s", e)
    except JSONDecodeError as e:
        logger.error("JSON 解析失败，回复/删除阶段：%s", e)

    # 2. 置顶
    time.sleep(3)
    try:
        top_data = {'BDUSS': bduss, 'fid': fid, 'tid': post_id, 'type': '1', 'tbs': tbs}
        resp = s.post(SET_TOP_URL,
                      data=encodeData(top_data),
                      headers=headers,
                      cookies=cookies,
                      timeout=10)
        logger.info("置顶响应 status=%s", resp.status_code)
        resp.raise_for_status()
        text = resp.text.strip()
        if not text:
            # 空响应，视为操作成功
            success_flag['top'] = True
            logger.info("置顶空响应，视为成功，tid=%s", post_id)
        else:
            try:
                jr = resp.json()
            except JSONDecodeError:
                logger.warning("置顶接口返回非 JSON 内容，text=%r", text)
            else:
                if jr.get('error_code') == '0':
                    success_flag['top'] = True
                    logger.info("置顶操作返回 error_code=0，成功，tid=%s", post_id)
                else:
                    logger.error("置顶操作失败，接口返回：%r", jr)
    except requests.exceptions.RequestException as e:
        logger.error("HTTP 异常，置顶阶段：%s", e)

    # 3. 取消置顶（不影响 success_flag）
    time.sleep(3)
    try:
        cancel_data = {'BDUSS': bduss, 'fid': fid, 'tid': post_id, 'type': '0', 'tbs': tbs}
        resp = s.post(SET_TOP_URL,
                      data=encodeData(cancel_data),
                      headers=headers,
                      cookies=cookies,
                      timeout=10)
        logger.info("取消置顶响应 status=%s", resp.status_code)
        resp.raise_for_status()
        logger.info("取消置顶成功，tid=%s", post_id)
    except Exception as e:
        logger.warning("取消置顶失败：%s", e)

    return success_flag


def format_time(seconds):
    # 转换时间格式
    minutes = seconds // 60
    remaining_seconds = seconds % 60

    if minutes > 0:
        return f"{minutes}分{remaining_seconds}秒"
    else:
        return f"{remaining_seconds}秒"

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
    subject = f"{time.strftime('%Y-%m-%d', time.localtime())} 签到{length}个贴吧账号"
    
    # 邮件正文加入账号信息和总签到时间
    body = f"<h2 style='color: #66ccff;'>签到报告 - {time.strftime('%Y年%m月%d日', time.localtime())}</h2>"
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
        # 标记用户账号（第几个账号）
        body += f"<br><b>账号{idx+1}的签到信息：</b><br><br>"
        
        for i in user_favorites:
            body += f"""
            <div class="child">
                <div class="name"> 贴吧名称: { i['name'] }</div>
                <div class="slogan"> 贴吧简介: { i['slogan'] }</div>
            </div>
            <hr>
            """
    
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
        logger.error("邮件发送失败：" + str(e))
    except Exception as e:
        logger.error("邮件发送时发生错误：" + str(e))
    

def main():
    if ('BDUSS' not in ENV):
        logger.error("未配置BDUSS")
        return
    b = ENV['BDUSS'].split('#')
    all_favorites = []  # 创建空列表存储所有用户的关注贴吧
    total_sign_time = 0  # 总签到时间
    task_status = []  # 初始化任务状态列表
    for n, i in enumerate(b, start=1):
        logger.info("开始签到第" + str(n) + "个用户")
        start_time = time.time()  # 记录用户签到开始时间
        tbs = get_tbs(i)
        favorites = get_favorite(i)
        for j in favorites:
            time.sleep(random.randint(1, 3))
            client_sign(i, tbs, j["id"], j["name"])
        logger.info("完成第" + str(n) + "个用户签到")
        end_time = time.time()  # 记录用户签到结束时间
        total_sign_time += int(end_time - start_time)  # 计算用户签到时间并累加到总签到时间
        all_favorites.append(favorites)  # 将每个用户的关注贴吧添加到 all_favorites 列表中

        if str(n-1) == ENV.get('MODERATOR_BDUSS_INDEX', '0'):
            moderated_bars = ENV.get('MODERATED_BARS', '').split(',')
            target_posts = ENV.get('TARGET_POST_IDS', '').split(',')
            
            for bar_name, post_id in zip(moderated_bars, target_posts):
                logger.info(f"开始处理吧主考核：{bar_name}")
                status = moderator_task(i, tbs, bar_name.strip(), post_id.strip())
                task_status.append(status)  # 收集状态
                time.sleep(5)

    send_email(all_favorites, total_sign_time, task_status)  # 将包含所有用户关注贴吧的列表和总签到时间传递
    logger.info("所有用户签到结束")


if __name__ == '__main__':
    main()
