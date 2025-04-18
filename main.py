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


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API_URL
LIKIE_URL = "http://c.tieba.baidu.com/c/f/forum/like"
TBS_URL = "http://tieba.baidu.com/dc/common/tbs"
SIGN_URL = "http://c.tieba.baidu.com/c/c/forum/sign"

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
        res = s.post(url=LIKIE_URL, data=data, timeout=10).json()
    except Exception as e:
        logger.error("获取关注的贴吧出错" + e)
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
            res = s.post(url=LIKIE_URL, data=data, timeout=10).json()
        except Exception as e:
            logger.error("获取关注的贴吧出错" + e)
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


# def client_sign(bduss, tbs, fid, kw):
#     # 客户端签到
#     logger.info("开始签到贴吧：" + kw)
#     data = copy.copy(SIGN_DATA)
#     data.update({BDUSS: bduss, FID: fid, KW: kw, TBS: tbs, TIMESTAMP: str(int(time.time()))})
#     data = encodeData(data)
#     res = s.post(url=SIGN_URL, data=data, timeout=10).json()
#     return res

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


def format_time(seconds):
    # 转换时间格式
    minutes = seconds // 60
    remaining_seconds = seconds % 60

    if minutes > 0:
        return f"{minutes}分{remaining_seconds}秒"
    else:
        return f"{remaining_seconds}秒"

def send_email(sign_list, total_sign_time):
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

    send_email(all_favorites, total_sign_time)  # 将包含所有用户关注贴吧的列表和总签到时间传递
    logger.info("所有用户签到结束")


if __name__ == '__main__':
    main()
