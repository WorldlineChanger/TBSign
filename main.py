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
import json

# -----------------------------
# 日志配置
# -----------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -----------------------------
# 设备指纹生成 (持久化)
# -----------------------------
import uuid

def gen_advanced_device():
    """生成一套新的设备指纹，包含真实设备特征"""
    # 真实IMEI算法（Luhn校验）
    def generate_valid_imei():
        imei_base = ''.join(random.choices('0123456789', k=14))
        # Luhn算法计算校验位
        def luhn_checksum(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            return checksum % 10
        check_digit = (10 - luhn_checksum(int(imei_base))) % 10
        return imei_base + str(check_digit)
    
    # 真实设备型号和对应的技术参数
    device_profiles = [
        {
            'model': 'MI 13', 'brand': 'Xiaomi', 'android': '13', 'sdk': '33',
            'cpu': 'Qualcomm SM8550-AB Snapdragon 8 Gen 2', 'resolution': '2400x1080'
        },
        {
            'model': 'Pixel 8', 'brand': 'Google', 'android': '14', 'sdk': '34',
            'cpu': 'Google Tensor G3', 'resolution': '2400x1080'
        },
        {
            'model': 'HUAWEI P50', 'brand': 'HUAWEI', 'android': '11', 'sdk': '30',
            'cpu': 'Kirin 9000', 'resolution': '2700x1224'
        },
        {
            'model': 'OnePlus 11', 'brand': 'OnePlus', 'android': '13', 'sdk': '33',
            'cpu': 'Qualcomm SM8550-AB Snapdragon 8 Gen 2', 'resolution': '3216x1440'
        },
        {
            'model': 'vivo X90', 'brand': 'vivo', 'android': '13', 'sdk': '33',
            'cpu': 'MediaTek Dimensity 9200', 'resolution': '2800x1260'
        }
    ]
    
    device = random.choice(device_profiles)
    rand_imei = generate_valid_imei()
    
    # 更复杂的客户端ID生成
    timestamp = int(time.time() * 1000)
    rand_suffix = uuid.uuid4().hex[:8]
    client_id = f"wappc_{timestamp}_{rand_suffix}"
    
    # 生成设备唯一标识CUID
    cuid = hashlib.md5(f"{rand_imei}_{device['model']}_{timestamp}".encode()).hexdigest()[:16]
    
    return {
        'imei': rand_imei,
        'model': device['model'],
        'brand': device['brand'],
        'android_version': device['android'],
        'sdk_version': device['sdk'],
        'cpu': device['cpu'],
        'resolution': device['resolution'],
        'client_id': client_id,
        'cuid': cuid
    }

# 全局设备指纹 - 持久化加载或生成
def get_persistent_device(filename="device_profile.json"):
    """从文件加载设备指纹，如果文件不存在则生成新的并保存"""
    try:
        with open(filename, 'r') as f:
            device = json.load(f)
            logger.info(f"从 {filename} 加载设备指纹")
            return device
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("设备指纹文件不存在或无效，生成新的指纹")
        device = gen_advanced_device()
        try:
            with open(filename, 'w') as f:
                json.dump(device, f, indent=4)
                logger.info(f"新设备指纹已保存到 {filename}")
        except Exception as e:
            logger.error(f"保存设备指纹失败: {e}")
        return device

DEVICE = get_persistent_device()
logger.info(f"当前设备指纹: {DEVICE['brand']} {DEVICE['model']}, IMEI={DEVICE['imei'][:4]}****, CUID={DEVICE['cuid']}")

# 高级UA生成器
def generate_realistic_ua(device_info):
    """基于设备信息生成UA"""
    android_version = device_info['android_version']
    model = device_info['model'].replace(' ', '%20')
    brand = device_info['brand']
    
    # Chrome版本池（移动端Chrome版本）
    chrome_versions = ['118.0.0.0', '119.0.0.0', '120.0.0.0', '121.0.0.0']
    chrome_ver = random.choice(chrome_versions)
    
    # WebKit版本与Chrome版本对应
    webkit_ver = '537.36'
    
    return f"Mozilla/5.0 (Linux; Android {android_version}; {model}) AppleWebKit/{webkit_ver} (KHTML, like Gecko) Chrome/{chrome_ver} Mobile Safari/{webkit_ver}"

USER_AGENTS_DESKTOP = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; rv:122.0) Gecko/20100101 Firefox/122.0',
]

# 动态UA管理
UA_REFRESH_CYCLE = 10
_current_mobile_ua = generate_realistic_ua(DEVICE)
_ua_counter = 0

def get_headers(is_mobile=False):
    """获取基础请求头，支持动态UA刷新"""
    global _ua_counter, _current_mobile_ua
    if is_mobile:
        _ua_counter += 1
        if _ua_counter % UA_REFRESH_CYCLE == 0:
            _current_mobile_ua = generate_realistic_ua(DEVICE)
        ua = _current_mobile_ua
        
        # 移动端特有的请求头
        headers = {
            'Host': 'c.tieba.baidu.com',
            'User-Agent': ua,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    else:
        ua = random.choice(USER_AGENTS_DESKTOP)
        headers = {
            'Host': 'tieba.baidu.com',
            'User-Agent': ua,
        }
    
    return headers

# -----------------------------
# API 地址
# -----------------------------
REPLY_URL   = "http://c.tieba.baidu.com/c/c/post/add"            # 回帖接口（移动端）
VIEW_POST_URL = "http://c.tieba.baidu.com/c/c/post/thread"       # 查看帖子接口（移动端）
DELETE_URL  = "http://c.tieba.baidu.com/c/u/comment/postDel"     # 删除回复接口
SET_TOP_URL = "http://tieba.baidu.com/mo/q"                      # 置顶/取消置顶接口
TBS_URL     = "http://tieba.baidu.com/dc/common/tbs"             # 获取 tbs
LIKIE_URL   = "http://c.tieba.baidu.com/c/f/forum/like"          # 获取关注贴吧接口
SIGN_URL    = "http://c.tieba.baidu.com/c/c/forum/sign"          # 签到接口

# -----------------------------
# 环境变量 & 开关
# -----------------------------
ENV                     = os.environ
DO_MODERATOR_TASK   = ENV.get('MODERATOR_TASK_ENABLE'  ,'false').lower() == 'true'
DO_MODERATOR_POST   = ENV.get('MODERATOR_POST_ENABLE'  ,'false').lower() == 'true'
DO_MODERATOR_TOP    = ENV.get('MODERATOR_TOP_ENABLE'   ,'false').lower() == 'true'
DO_MODERATOR_DELETE = ENV.get('MODERATOR_DELETE_ENABLE','false').lower() == 'true'  # 是否删除回复
MODERATOR_BDUSS_INDEX   = ENV.get('MODERATOR_BDUSS_INDEX', '0')
MODERATED_BARS          = ENV.get('MODERATED_BARS', '')
TARGET_POST_IDS         = ENV.get('TARGET_POST_IDS', '')
PROXY_ENABLE            = ENV.get('PROXY_ENABLE', 'false').lower() == 'true'  # 是否使用代理
SOCKS_PROXY             = ENV.get('SOCKS_PROXY', '')  # 首选代理

# -----------------------------
# 请求签名 & 常量
# -----------------------------
COOKIE       = "Cookie"
BDUSS        = "BDUSS"
SIGN_KEY     = 'tiebaclient!!!'
UTF8         = "utf-8"

# 基础签名数据（使用高级设备指纹）
SIGN_DATA    = {
    '_client_type': '2',
    '_client_version': '12.18.1.0',
    '_phone_imei': DEVICE['imei'],
    'model': DEVICE['model'],
    'net_type': '1',
    '_client_id': DEVICE['client_id'],
    'cuid': DEVICE['cuid'],
}

# 全局 Session
s = requests.Session()

# -----------------------------
# 代理管理器 (核心重构)
# -----------------------------
class ProxyManager:
    def __init__(self, enable, user_proxy):
        self.enable = enable
        self.user_proxy = user_proxy
        self.backup_proxies = []
        self.current_proxy_info = "无代理 (原始IP)"
        if not self.enable:
            logger.info("代理功能已禁用")

    def _sanitize_proxy_url(self, url):
        """隐藏代理信息"""
        if not url or '@' not in url or '//' not in url:
            return url
        try:
            protocol, rest = url.split('//', 1)
            creds, host_info = rest.split('@', 1)
            if ':' in creds:
                user, _ = creds.split(':', 1)
                return f"{protocol}//{user}:***@{host_info}"
            else: # 兼容无密码格式 user@host
                return f"***@{host_info}"
        except ValueError:
            # 解析失败，返回原始URL以避免崩溃
            return url
        return url

    def get_proxy(self):
        """获取一个可用的代理配置"""
        if not self.enable:
            return None

        # 1. 尝试首选代理
        if self.user_proxy:
            safe_proxy_url = self._sanitize_proxy_url(self.user_proxy)
            logger.info(f"尝试使用首选代理: {safe_proxy_url}")
            if self.test_proxy(self.user_proxy):
                self.current_proxy_info = f"首选代理: {safe_proxy_url}"
                return {'http': self.user_proxy, 'https': self.user_proxy}
            else:
                logger.warning("首选代理连接失败")
                self.user_proxy = None  # 标记为失败，不再尝试

        # 2. 尝试备用代理池
        if not self.backup_proxies:
            self.fetch_backup_proxies()
        
        while self.backup_proxies:
            backup_proxy = self.backup_proxies.pop(0)
            logger.info(f"尝试使用备用代理: {backup_proxy}")
            if self.test_proxy(backup_proxy):
                self.current_proxy_info = f"备用代理: {backup_proxy}"
                return {'http': backup_proxy, 'https': backup_proxy}
            else:
                logger.warning("备用代理连接失败")

        # 3. 降级至无代理
        self.current_proxy_info = "无代理 (降级)"
        logger.error("所有代理尝试失败，降级为无代理IP")
        self.enable = False # 彻底关闭代理功能
        return None

    def fetch_backup_proxies(self):
        """从 ProxyScrape 获取备用 SOCKS5 代理列表"""
        logger.info("正在从 ProxyScrape 获取备用代理...")
        url = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                proxies = [f"socks5h://{p}" for p in resp.text.strip().split('\r\n') if p]
                random.shuffle(proxies)
                self.backup_proxies = proxies
                logger.info(f"成功获取 {len(self.backup_proxies)} 个备用代理")
            else:
                logger.warning("获取备用代理失败，API 返回状态码非 200")
        except Exception as e:
            logger.error(f"获取备用代理时发生网络错误: {e}")

    def test_proxy(self, proxy_url):
        """测试代理是否能连接到 ipinfo.io"""
        try:
            import socks
            proxies = {'http': proxy_url, 'https': proxy_url}
            # 使用全球稳定的IP信息服务进行测试
            test_url = "https://ipinfo.io/ip"
            resp = requests.get(test_url, proxies=proxies, timeout=10)
            if resp.status_code == 200:
                logger.info(f"代理测试成功，出口 IP: {resp.text.strip()}")
                return True
            return False
        except ImportError:
            if not getattr(self, '_pysocks_warning_logged', False):
                logger.warning("未安装 PySocks 库 (pip install PySocks)，SOCKS5 代理将不会生效")
                self._pysocks_warning_logged = True
            return False
        except Exception as e:
            logger.debug(f"代理测试失败: {self._sanitize_proxy_url(proxy_url)}, error: {e}")
            return False

# 初始化代理管理器
proxy_manager = ProxyManager(PROXY_ENABLE, SOCKS_PROXY)

def robust_request(method, url, **kwargs):
    """
    使用代理管理器进行健壮的网络请求，支持失败重试和代理切换。
    """
    max_retries = 3
    for attempt in range(max_retries):
        proxies = proxy_manager.get_proxy()
        kwargs['proxies'] = proxies
        try:
            # 确保 User-Agent 在重试时也能获取
            if 'headers' not in kwargs:
                kwargs['headers'] = get_headers()
            
            if method.upper() == 'GET':
                resp = s.get(url, **kwargs)
            else:
                resp = s.post(url, **kwargs)
            
            resp.raise_for_status() # 对非2xx状态码抛出异常
            return resp
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求失败 (第 {attempt+1}/{max_retries} 次): {e}")
            if attempt < max_retries - 1:
                time.sleep(2) # 重试前等待
            else:
                logger.error("请求达到最大重试次数，彻底失败")
                raise # 将异常重新抛出，让上层逻辑处理

# -----------------------------
# 风控检测函数
# -----------------------------
def check_wind_control(resp_json):
    """
    检测是否触发风控，根据常见 error_code 暂停。
    返回 True 表示触发风控并已退避。
    """
    ec = str(resp_json.get('error_code', ''))
    # 常见需要验证码/被限制的错误码，可根据抓包继续补充
    if ec in ('110', '221023', '219016', '4', '220034'):
        logger.warning(f"触发风控({ec})，暂停5分钟")
        time.sleep(300)
        return True
    return False

# -----------------------------
# 构造随机回复内容（保持原版格式）
# -----------------------------
import uuid
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))  # 北京时间
NOISE_CHARS = ['​', '‌', '⁠', '᠎']  # 零宽/特殊空白字符
SCI_FI_PHRASES = [
    'IBN-5100 校准中',
    '世界线变动率 0.337%',
    'D-Mail 已发送',
    'Operation Skuld √',
    'MAGI 决断 √',
    'EVA 启动待命',
    'AT 力场稳定',
    'Phase Shift Online',
    'Laplace Demon 解析',
    'EXAM 系统运行',
    'LCL 循环正常',
    'Dirac Sea 连接',
    'Geass 已授予',
    '同步率 400%↑',
    'Twin Drive 共振',
    'Quantization Complete',
    'GUTS 收到',
]

HITOKOTO_URLS = [
    'https://v1.hitokoto.cn/?encode=json',
    'https://international.v1.hitokoto.cn/?encode=json',
]

def get_hitokoto():
    """调用一言 API 获取随机句子（备用域名，多轮重试）"""
    for attempt in range(3):  # 三轮
        for url in HITOKOTO_URLS:  # 每轮依次尝试两个域名
            try:
                resp = robust_request(
                    'GET',
                    url,
                    headers={'User-Agent': random.choice(USER_AGENTS_DESKTOP)},
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    qt  = (data.get('hitokoto') or '').strip()
                    frm = (data.get('from') or '').strip()
                    who = (data.get('from_who') or '').strip()
                    if qt:
                        if frm and who:
                            return f"{qt}\n——{frm} · {who}"
                        elif frm:
                            return f"{qt}\n——{frm}"
                        else:
                            return qt
            except Exception:
                pass
        # 本轮两域名都失败，若还可重试，就退避 1~2 秒
        if attempt < 2:
            time.sleep(random.uniform(1, 2))
    return ''

def build_reply_content():
    """生成随机化回复内容，含北京时间、零宽符、短句、一言"""
    now_str = datetime.now(CN_TZ).strftime('%Y年%m月%d日 %H时%M分%S秒')
    first_line = f"世界线 - {now_str} #(滑稽)"

    noise = ''.join(random.choice(NOISE_CHARS) for _ in range(random.randint(1,3)))
    sci_phrase = random.choice(SCI_FI_PHRASES)
    rand_token = uuid.uuid4().hex[:6]
    second_line = f"{noise}{sci_phrase}-{rand_token}"

    quote = get_hitokoto()
    if quote:
        # 使用 `/>` 为分隔，避免双换行被折叠
        quote_block = f"\n/>\n{quote}"
    else:
        quote_block = ''

    return f"{first_line}\n{second_line}{quote_block}"

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
            resp = robust_request('GET', TBS_URL, headers=headers, timeout=5)
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
    """获取用户关注的贴吧列表（稳健分页 + 扁平化 + 去重 + 字段规范化）"""
    logger.info("获取关注的贴吧开始")
    collected = []
    seen = set()
    page_no = 1

    def _normalize(item: dict):
        """规范化单条数据，确保包含 id / name 字段"""
        if not isinstance(item, dict):
            return None
        fid = str(item.get('id') or item.get('fid') or item.get('forum_id') or '').strip()
        name = item.get('name') or item.get('fname') or item.get('forum_name')
        if not fid or not name:
            return None
        # 复制并补全标准键
        obj = dict(item)
        obj['id'] = fid
        obj['name'] = str(name)
        return obj

    def _add(item):
        obj = _normalize(item)
        if not obj:
            return
        fid = obj['id']
        if fid in seen:
            return
        seen.add(fid)
        collected.append(obj)

    while True:
        data = {
            'BDUSS': bduss,
            '_client_type': '2',
            '_client_id': DEVICE['client_id'],
            '_client_version': SIGN_DATA['_client_version'],
            '_phone_imei': DEVICE['imei'],
            'cuid': DEVICE['cuid'],
            'from': '1008621y',
            'page_no': str(page_no),
            'page_size': '200',
            'model': DEVICE['model'],
            'net_type': '1',
            'timestamp': str(int(time.time())),
            'vcode_tag': '11',
        }
        data = encodeData(data)
        try:
            resp = robust_request('POST', LIKIE_URL, data=data, timeout=10)
            resp.raise_for_status()
            res = resp.json()
        except Exception as e:
            logger.error("获取关注的贴吧出错: %s", e)
            break

        flist = res.get('forum_list', {})
        if not isinstance(flist, dict):
            flist = {}
        # 兼容不同结构：可能是 list、list[list]、或单 dict
        for section in ('non-gconforum', 'gconforum'):
            v = flist.get(section, [])
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, list):
                        for sub in item:
                            _add(sub)
                    else:
                        _add(item)
            elif isinstance(v, dict):
                _add(v)

        logger.info(f"第{page_no}页累计收集 {len(collected)} 个")
        has_more = (str(res.get('has_more', '0')) == '1')  # 兼容整型/字符串
        if not has_more:
            break
        page_no += 1
        time.sleep(0.2)  # 轻微间隔

    logger.info("获取关注的贴吧结束，共 %d 个", len(collected))
    return collected

# -----------------------------
# 3. 客户端签到
# -----------------------------
def client_sign(bduss, tbs, fid, kw):
    """执行签到操作"""
    logger.info(f"签到贴吧: {kw}")
    data = {**SIGN_DATA, 'BDUSS': bduss, 'fid': fid, 'kw': kw, 'tbs': tbs, 'timestamp': str(int(time.time()))}
    resp = robust_request('POST', SIGN_URL, headers=get_headers(), cookies={BDUSS: bduss}, data=encodeData(data), timeout=10)
    try:
        jr = resp.json()
        if check_wind_control(jr):
            return jr
        return jr
    except JSONDecodeError:
        return {'error_code': 0}

# -----------------------------
# 4. 吧主任务：回复+删除 & 置顶/取消置顶（优化版）
# -----------------------------
def simulate_view_post(bduss, fid, tid):
    """模拟浏览帖子，为后续操作预热"""
    logger.info(f"模拟浏览帖子: tid={tid}")
    view_data = {
        'BDUSS': bduss,
        'fid': fid,
        'tid': tid,
        'pn': '1', # 页码
        'rn': '20', # 每页数量
        'with_floor': '1',
        'lp': '6',
        'see_lz': '0', # 是否只看楼主
        'tbs': get_tbs(bduss), # 查看帖子也需要 tbs
        '_client_type': '2',
        '_client_version': SIGN_DATA['_client_version'],
        '_phone_imei': DEVICE['imei'],
        'model': DEVICE['model'],
        '_client_id': DEVICE['client_id'],
        'cuid': DEVICE['cuid'],
        'net_type': '1',
        'timestamp': str(int(time.time())),
    }
    try:
        resp = robust_request('POST', VIEW_POST_URL,
            headers=get_headers(is_mobile=True),
            cookies={BDUSS: bduss},
            data=encodeData(view_data),
            timeout=10,
        )
        logger.info(f"模拟浏览完成 status={resp.status_code}")
        return True
    except Exception as e:
        logger.warning(f"模拟浏览失败: {e}")
        return False

def moderator_task(bduss, tbs, bar_name, post_id):
    """执行吧主考核任务，采用防检测措施"""
    success = {'reply': False, 'top': False}
    if not DO_MODERATOR_TASK:
        return success
    # 开始吧主任务日志
    logger.info(f"开始吧主任务: {bar_name}, post_id={post_id}")
    try:
        fid = get_fid_by_name(bduss, bar_name)
    except Exception as e:
        logger.error(f"获取 fid 失败: {e}")
        return success
    cookies = {BDUSS: bduss}
    def rnd_sleep(): time.sleep(random.uniform(3, 8))
    
    # 1. 模拟浏览 (预热)
    simulate_view_post(bduss, fid, post_id)
    rnd_sleep() # 浏览后随机停顿

    # 2. 回复 & 删除（增强防检测）
    if DO_MODERATOR_POST:
        content = build_reply_content()
        logger.info(f"回复内容: {content}")
        
        # 构造完整的防检测参数
        current_timestamp = int(time.time())
        current_timestamp_ms = int(time.time() * 1000)
        
        reply_data = {
            'BDUSS': bduss,
            'content': content,
            'fid': fid,
            'tid': post_id,
            # 'kw': bar_name,
            'tbs': tbs,
            '_client_type': '2',
            '_client_version': SIGN_DATA['_client_version'],
            '_phone_imei': DEVICE['imei'],
            'model': DEVICE['model'],
            '_client_id': DEVICE['client_id'],
            'cuid': DEVICE['cuid'],
            'net_type': '1',
            'timestamp': str(current_timestamp),
            'vcode_tag': '11',
            'is_adlay': '1',
            'mouse_pwd_t': str(current_timestamp_ms),
            'mouse_pwd': str(current_timestamp_ms),
        }
        
        rnd_sleep()
        resp = robust_request('POST', REPLY_URL,
            headers=get_headers(is_mobile=True),
            cookies=cookies,
            data=encodeData(reply_data),
            timeout=15,
        )
        try:
            jr = resp.json()
            logger.info(f"回复接口返回: {jr}")
            if check_wind_control(jr):
                return success
            if str(jr.get('error_code', '')) == '0' or jr.get('msg') == '发送成功':
                success['reply'] = True
                pid = jr.get('data', {}).get('post_id') or jr.get('pid')
                logger.info(f"回复成功 pid={pid}")
                # 删除回复
                if DO_MODERATOR_DELETE and pid:
                    rnd_sleep()
                    del_data = {
                        'BDUSS': bduss,
                        'post_id': pid, 
                        'del_type': '0', 
                        'tbs': tbs,
                        '_client_type': '2',
                        '_client_version': SIGN_DATA['_client_version'],
                        '_phone_imei': DEVICE['imei'],
                        'model': DEVICE['model'],
                        'cuid': DEVICE['cuid'],
                        'timestamp': str(int(time.time())),
                    }
                    del_resp = robust_request('POST', DELETE_URL,
                        headers=get_headers(is_mobile=True),
                        cookies=cookies,
                        data=encodeData(del_data),
                        timeout=10,
                    )
                    try:
                        jr_del = del_resp.json()
                        logger.info(f"删除回复 status={del_resp.status_code}, response: {jr_del}")
                    except JSONDecodeError:
                        logger.info(f"删除回复 status={del_resp.status_code}, 无 JSON 返回")
                else:
                    logger.info("删除操作已关闭或 pid 缺失")
            else:
                logger.error(f"回复失败: {jr}")
        except Exception as e:
            logger.error(f"回复/删除阶段失败: {e}")
    else:
        logger.info("发帖操作已关闭")
    
    # 2. 置顶 & 取消置顶
    if DO_MODERATOR_TOP:
        rnd_sleep()
        resp_top = robust_request('GET', SET_TOP_URL,
            headers=get_headers(is_mobile=True),
            cookies=cookies,
            params={'tn':'bdTOP','z':post_id,'tbs':tbs,'word':bar_name},
        )
        logger.info(f"置顶返回 status={resp_top.status_code}")
        success['top'] = True
        rnd_sleep()
        resp_untop = robust_request('GET', SET_TOP_URL,
            headers=get_headers(is_mobile=True),
            cookies=cookies,
            params={'tn':'bdUNTOP','z':post_id,'tbs':tbs,'word':bar_name},
        )
        logger.info(f"取消置顶返回 status={resp_untop.status_code}")
    else:
        logger.info("置顶操作已关闭")
    return success

# -----------------------------
# 5. 邮件汇报函数
# -----------------------------
def send_email(sign_list, total_sign_time, task_status):
    """
    发送日报邮件，包含签到报告和吧主任务状态
    """
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
    body += f"""
    <div style='background-color: #f0f8ff; padding: 10px; margin: 10px 0; border-left: 4px solid #4a90e2;'>
        <h4>设备信息</h4>
        <ul>
            <li>设备型号: {DEVICE['brand']} {DEVICE['model']}</li>
            <li>IMEI: {DEVICE['imei'][:4]}****{DEVICE['imei'][-4:]}</li>
            <li>CUID: {DEVICE['cuid'][:8]}...</li>
            <li>客户端版本: {SIGN_DATA['_client_version']}</li>
            <li>代理状态: {proxy_manager.current_proxy_info}</li>
        </ul>
    </div>
    """
    if moderated_bars:
        body += "<h3>吧主考核任务执行情况：</h3>"
        for bar_name, status in zip(moderated_bars, task_status):
            # 发帖状态判断
            if not DO_MODERATOR_TASK or not DO_MODERATOR_POST:
                post_text = '取消'
            elif status['reply']:
                post_text = '成功'
            else:
                post_text = '失败'
            # 置顶状态判断
            if not DO_MODERATOR_TASK or not DO_MODERATOR_TOP:
                top_text = '取消'
            elif status['top']:
                top_text = '成功'
            else:
                top_text = '失败'
            icon = '✅' if status['reply'] or status['top'] else '❌'
            body += (
                f"<div class=\"child\">"
                f"{bar_name}：{icon}<br>"
                f"发帖操作：{post_text}<br>"
                f"置顶操作：{top_text}"
                f"</div>"
            )
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
    for idx, user_favorites in enumerate(sign_list, start=1):
        body += f"<br><b>账号{idx}的签到信息：</b><br><br>"
        for i in user_favorites:
            body += (
                f"<div class=\"child\">"
                f"<div class=\"name\">贴吧名称: {i['name']}</div>"
                f"<div class=\"slogan\">贴吧简介: {i.get('slogan','无')}</div>"
                f"</div><hr>"
            )
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
        resp = robust_request('GET', url, headers=headers, timeout=10)
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
    interval_days = int(ENV.get('MODERATOR_INTERVAL_DAYS', '10'))
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
                time.sleep(random.uniform(6, 12))
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
