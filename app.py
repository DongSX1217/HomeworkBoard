import flask
from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify, make_response, Response, send_from_directory
import base64, time, json, re, os, uuid, threading, requests, smtplib, sys, random
import http.client
from datetime import datetime, timedelta
from openai import OpenAI
import logging
import traceback
import ipaddress

# 导入配置
try:
    from config import config, Config
except ImportError:
    # 如果配置文件不存在，使用默认配置
    class Config:
        SECRET_KEY = 'test_key'
        DATA_DIR = 'data'
        DEBUG = False
        LOG_DIR = os.path.join(DATA_DIR, 'logs')
        ERROR_LOG_FILE = os.path.join(LOG_DIR, 'error.log')
        clear_password = 'test'
        AI_SYSTEM_EDIT_PASSWORD = 'test'
        AI_SYSTEM_SEE_PASSWORD = 'test'
        
        @staticmethod
        def init_app(app):
            if not os.path.exists(Config.DATA_DIR):
                os.makedirs(Config.DATA_DIR)
            if not os.path.exists(Config.LOG_DIR):
                os.makedirs(Config.LOG_DIR)
    
    config = {'default': Config}

app = Flask(__name__) # 创建 Flask 应用

# 配置应用
config_type = os.environ.get('FLASK_CONFIG', 'default')
app.config.from_object(config[config_type])

# 初始化配置
Config.init_app(app)

# 设置日志记录器
if not app.config.get('DEBUG', False):
    # 在非调试模式下，记录错误日志到文件
    error_logger = logging.getLogger('error_logger')
    error_logger.setLevel(logging.ERROR)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(Config.ERROR_LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.ERROR)
    
    # 创建日志格式
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    error_logger.addHandler(file_handler)
else:
    error_logger = None

@app.errorhandler(Exception)
def handle_exception(e):
    # 记录错误日志
    if error_logger and not app.config.get('DEBUG', False):
        error_logger.error(f"Error: {str(e)}\nTraceback: {traceback.format_exc()}")
    
    # 在调试模式下，仍然显示默认的错误页面
    if app.config.get('DEBUG', False):
        raise e
    
    # 在生产环境中，渲染自定义错误页面
    return render_template('error.html', error=str(e)), 500

@app.errorhandler(404)
def not_found_error(e):
    # 处理404错误
    return render_template('error.html', error="请求的页面不存在"), 404

app.secret_key = 'test_key'  # 生产环境中使用强密钥

@app.context_processor
def inject_subject_class(): # 注入Subject类到模板
    return dict(Subject=Subject) # 返回一个包含Subject类的字典

# 确保data目录存在
if not os.path.exists(Config.DATA_DIR):
    os.makedirs(Config.DATA_DIR)
if not os.path.exists(Config.LOG_DIR):
    os.makedirs(Config.LOG_DIR)

DATA_FILE = os.path.join(Config.DATA_DIR, 'submissions.json')
LABELS_FILE = os.path.join(Config.DATA_DIR, 'labels.json')
SUBJECTS_FILE = os.path.join(Config.DATA_DIR, 'subjects.json')
IP_FILE = os.path.join(Config.DATA_DIR, 'ips.json')
STUDENTS_FILE = os.path.join(Config.DATA_DIR, 'students.json')
PASSWORD_FILE = os.path.join(Config.DATA_DIR, 'password.json')
NOTICE_FILE = os.path.join(Config.DATA_DIR, 'notices.json')

LOG_FILE = os.path.join(Config.LOG_DIR, 'operation.log')
LOGIN_LOG_FILE = os.path.join(Config.LOG_DIR, 'login.log')
INPUT_LOG_FILE = os.path.join(Config.LOG_DIR, 'input.log')

default_labels = [
  {
    "id": 1,
    "name": "课前由科代表或小组长检查",
    "color": "#3498db"
  },
  {
    "id": 2,
    "name": "课前由授课教师检查",
    "color": "#3498db"
  },
  {
    "id": 3,
    "name": "小组任务",
    "color": "#3498db"
  },
  {
    "id": 4,
    "name": "自行核对答案",
    "color": "#9a8e0e"
  },
  {
    "id": 5,
    "name": "复习作业",
    "color": "#3498db"
  },
  {
    "id": 6,
    "name": "预习作业",
    "color": "#3498db"
  },
  {
    "id": 7,
    "name": "拓展任务",
    "color": "#9f6019"
  },
  {
    "id": 8,
    "name": "选做",
    "color": "#2eba1c"
  },
  {
    "id": 9,
    "name": "教师布置",
    "color": "#3498db"
  },
  {
    "id": 0,
    "name": "未知标签",
    "color": "#808080"
  }
]

def load_submissions():
    """从JSON文件加载提交数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_submissions(submissions):
    """将提交数据保存到JSON文件"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(submissions, f, ensure_ascii=False, indent=2)

def save_labels(labels):
    """将标签数据保存到JSON文件"""
    with open(LABELS_FILE, 'w', encoding='utf-8') as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)

def log_operation(operation, details, ip_address):
    """记录操作日志到文件"""
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "operation": operation,
        "details": details,
        "ip_address": ip_address
    }
    
    # 确保日志目录存在
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 追加写入日志
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

def log_login(name, student_id, ip_address):
    """记录登录日志到文件"""
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "name": name,
        "student_id": student_id,
        "ip_address": ip_address
    }
    
    # 确保日志目录存在
    log_dir = os.path.dirname(LOGIN_LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 追加写入日志
    with open(LOGIN_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

def log_input(content, name, student_id, ip_address, anonymous):
    """记录用户输入到文件"""
    # 加载现有数据
    if os.path.exists(INPUT_LOG_FILE):
        with open(INPUT_LOG_FILE, 'r', encoding='utf-8') as f:
            try:
                inputs = json.load(f)
            except json.JSONDecodeError:
                inputs = []
    else:
        inputs = []
    
    # 添加新输入
    input_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": content,
        "name": name,
        "student_id": student_id,
        "ip_address": ip_address,
        "anonymous": anonymous
    }
    
    inputs.append(input_entry)
    
    # 保存数据
    with open(INPUT_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(inputs, f, ensure_ascii=False, indent=2)

def load_inputs():
    """从文件加载所有用户输入"""
    if os.path.exists(INPUT_LOG_FILE):
        with open(INPUT_LOG_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def check_submit_limit(name, student_id):
    """检查用户提交限制"""
    inputs = load_inputs()
    
    # 获取当前时间和24小时前的时间
    now = datetime.now()
    past_24_hours = now - timedelta(hours=24)
    
    # 统计用户提交次数
    user_submissions_24h = []
    user_submissions_30s = []
    
    for input_entry in inputs:
        # 检查是否是同一用户
        if input_entry.get('name') == name and input_entry.get('student_id') == student_id:
            # 解析时间戳
            try:
                entry_time = datetime.strptime(input_entry['timestamp'], "%Y-%m-%d %H:%M:%S")
                
                # 统计24小时内的提交
                if entry_time >= past_24_hours:
                    user_submissions_24h.append(input_entry)
                    
                # 统计30秒内的提交
                if entry_time >= now - timedelta(seconds=30):
                    user_submissions_30s.append(input_entry)
            except ValueError:
                # 时间戳格式不正确，跳过该条目
                continue
    
    # 返回检查结果
    return {
        'within_30s': len(user_submissions_30s) >= 1,  # 30秒内是否有提交
        'within_24h': len(user_submissions_24h) >= 15  # 24小时内是否达到上限
    }

def save_password_data():
    """保存密码数据到文件"""
    with open(PASSWORD_FILE, 'w', encoding='utf-8') as f:
        json.dump(password_data, f, ensure_ascii=False, indent=4)

def get_default_password():
    """获取默认密码"""
    return "0000"

def validate_password(password):
    """验证密码格式"""
    if len(password) < 4 or len(password) > 16:
        return False, "密码长度必须在4-16位之间"
    return True, "密码格式正确"

def log_prompt_operation(operation, details, user_identifier, ip_address):
    """记录提示词操作日志到文件"""
    PROMPT_LOG_FILE = os.path.join(Config.LOG_DIR, 'prompt.log')
    
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "operation": operation,
        "details": details,
        "user_identifier": user_identifier,
        "ip_address": ip_address
    }
    
    # 确保日志目录存在
    log_dir = os.path.dirname(PROMPT_LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 追加写入日志
    with open(PROMPT_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

def log_input(content, name, student_id, ip_address, anonymous):
    """记录用户输入到文件"""
    # 加载现有数据
    if os.path.exists(INPUT_LOG_FILE):
        with open(INPUT_LOG_FILE, 'r', encoding='utf-8') as f:
            try:
                inputs = json.load(f)
            except json.JSONDecodeError:
                inputs = []
    else:
        inputs = []
    
    # 添加新输入
    input_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": content,
        "name": name,
        "student_id": student_id,
        "ip_address": ip_address,
        "anonymous": anonymous
    }
    
    inputs.append(input_entry)
    
    # 保存数据
    with open(INPUT_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(inputs, f, ensure_ascii=False, indent=2)

# 添加文件上传日志记录函数
def log_file_upload(filename, upload_path, file_size, user_name, user_id, ip_address):
    """记录文件上传日志到文件"""
    UPLOAD_LOG_FILE = os.path.join(Config.LOG_DIR, 'upload.log')
    
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filename": filename,
        "upload_path": upload_path,
        "file_size": file_size,
        "user_name": user_name,
        "user_id": user_id,
        "ip_address": ip_address
    }
    
    # 确保日志目录存在
    log_dir = os.path.dirname(UPLOAD_LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 追加写入日志
    with open(UPLOAD_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

# 添加检查用户上传配额的函数
def check_user_upload_quota(name, student_id, file_size):
    """检查用户上传配额（每月限制）"""
    UPLOAD_LOG_FILE = os.path.join(Config.LOG_DIR, 'upload.log')
    
    # 如果日志文件不存在，说明用户没有上传过文件
    if not os.path.exists(UPLOAD_LOG_FILE):
        return True, ""
    
    try:
        with open(UPLOAD_LOG_FILE, 'r', encoding='utf-8') as f:
            logs = [json.loads(line) for line in f if line.strip()]
    except:
        return True, ""
    
    # 计算当前月份
    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    
    # 计算用户本月上传的总大小
    user_monthly_usage = 0
    for log in logs:
        # 检查是否是该用户的记录
        if log.get('user_name') == name and log.get('user_id') == student_id:
            # 检查是否是本月的记录
            log_date = datetime.strptime(log.get('timestamp', ''), "%Y-%m-%d %H:%M:%S")
            if log_date.strftime("%Y-%m") == current_month:
                user_monthly_usage += log.get('file_size', 0)
    
    # 2GB 限制 (2 * 1024 * 1024 * 1024 bytes)
    quota_limit = 2 * 1024 * 1024 * 1024
    
    # 检查加上当前文件是否会超出配额
    if user_monthly_usage + file_size > quota_limit:
        remaining_quota = quota_limit - user_monthly_usage
        return False, f"本月上传配额不足。您本月还可上传 {remaining_quota / (1024*1024):.2f} MB"
    
    return True, ""

def get_file_tree(root_path, relative_path=''):
    """获取文件树结构"""
    items = []
    full_path = os.path.join(root_path, relative_path.lstrip('/'))
    
    if not os.path.exists(full_path):
        return items
        
    try:
        entries = os.listdir(full_path)
        for entry in entries:
            entry_path = os.path.join(full_path, entry)
            relative_entry_path = os.path.join(relative_path, entry).replace('\\', '/')
            static_entry_path = os.path.join('/static/file', relative_entry_path.lstrip('/')).replace('\\', '/')
            
            if os.path.isdir(entry_path):
                # 递归获取子目录内容
                sub_items = get_file_tree(root_path, relative_entry_path)
                items.append({
                    'type': 'directory',
                    'name': entry,
                    'path': relative_entry_path if relative_entry_path.startswith('/') else '/' + relative_entry_path,
                    'items': len(sub_items)
                })
            else:
                items.append({
                    'type': 'file',
                    'name': entry,
                    'path': static_entry_path,
                    'size': os.path.getsize(entry_path)
                })
    except Exception as e:
        print(f"Error reading directory {full_path}: {e}")
    
    # 按类型和名称排序，文件夹在前，文件在后，都按名称排序
    items.sort(key=lambda x: (x['type'] == 'file', x['name'].lower()))
    return items
def check_ip(ip, ip_list):
    """
    检查IP是否被封禁，支持CIDR格式
    :param ip: 要检查的IP地址
    :param ip_list: IP列表，可以包含单独IP或CIDR格式的IP段
    :return: 如果ip属于ip_list返回True，否则返回False
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        for ip_entry in ip_list:
            try:
                # 尝试解析为IP网络（CIDR格式）
                if '/' in ip_entry:
                    network = ipaddress.ip_network(ip_entry, strict=False)
                    if ip_obj in network:
                        return True
                else:
                    # 单个IP地址
                    if ip == ip_entry:
                        return True
            except ValueError:
                # 如果解析失败，当作普通字符串比较
                if ip == ip_entry:
                    return True
        return False
    except ValueError:
        # 如果IP地址无效，返回False
        return False

# 初始化数据
submissions = load_submissions()

if os.path.exists(IP_FILE):
    with open(IP_FILE, 'r', encoding='utf-8') as f:
        try:
            data_ip = json.load(f)
        except json.JSONDecodeError:
            pass

# 初始化学生数据
if os.path.exists(STUDENTS_FILE):
    with open(STUDENTS_FILE, 'r', encoding='utf-8') as f:
        try:
            students_data = json.load(f)
            # 确保students_data是字典类型
            if isinstance(students_data, list):
                # 如果是列表，转换为字典格式
                students_data = {item.get('name', ''): item.get('student_id', '') for item in students_data if isinstance(item, dict)}
                # 保存修复后的数据
                with open(STUDENTS_FILE, 'w', encoding='utf-8') as f_save:
                    json.dump(students_data, f_save, ensure_ascii=False, indent=4)
            elif not isinstance(students_data, dict):
                # 如果既不是字典也不是列表，使用默认数据
                students_data = {
                    "张三": "2023001",
                    "李四": "2023002"
                }
                with open(STUDENTS_FILE, 'w', encoding='utf-8') as f_save:
                    json.dump(students_data, f_save, ensure_ascii=False, indent=4)
        except json.JSONDecodeError:
            students_data = {}
else:
    # 如果没有学生数据文件，创建一个示例
    students_data = {
        "张三": "2023001",
        "李四": "2023002"
    }
    with open(STUDENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(students_data, f, ensure_ascii=False, indent=4)

# 初始化输入数据文件
if not os.path.exists(INPUT_LOG_FILE):
    with open(INPUT_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=4)

# 初始化密码数据
if os.path.exists(PASSWORD_FILE):
    with open(PASSWORD_FILE, 'r', encoding='utf-8') as f:
        try:
            password_data = json.load(f)
            # 确保password_data是字典类型
            if not isinstance(password_data, dict):
                password_data = {}
                print(f"密码文件格式错误，已创建一个空的密码文件。")
        except json.JSONDecodeError as e:
            password_data = {}
            print(f"密码文件格式错误，错误为{e}，已创建一个空的密码文件。")
else:
    # 如果没有密码文件，创建一个空的
    password_data = {}
    with open(PASSWORD_FILE, 'w', encoding='utf-8') as f:
        json.dump(password_data, f, ensure_ascii=False, indent=4)

@app.route('/')
@app.route('/home')
def homepage():
    return render_template('home.html')

@app.route('/api/news')
def get_news():
    """异步获取新闻的API接口"""
    from get_xinhuanet import get_xinhuanet
    get_xinhuanet_result = get_xinhuanet(lists=1)
    if get_xinhuanet_result.get('status') == 'error':
        app.logger.error(f"获取新华网新闻失败: {get_xinhuanet_result.get('message')}")
        return jsonify({'status': 'error', 'message': '获取新闻失败'})
    
    news = get_xinhuanet_result.get('result', {}).get('head_news', [])
    if news:
        # 只返回第一条新闻
        first_news = news[0]
        return jsonify({
            'status': 'success', 
            'news_url': first_news.get('url'), 
            'news_title': first_news.get('title')
        })
    else:
        return jsonify({'status': 'error', 'message': '未获取到新闻'})

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/clock')
def clock_page():
    return render_template('clock.html')

@app.route('/image')
def image_page():
    return render_template('image.html')

@app.route('/class_schedule')
def class_schedule_page():
    return render_template('class_schedule.html')

@app.route('/countdown')
def countdown_page():
    return render_template('countdown.html')

@app.route('/file')
def file_browser():
    """文件浏览页面"""
    return render_template('file/index.html')

@app.route('/api/files')
def api_files():
    """获取文件列表的API"""
    path = request.args.get('path', '/')
    file_root = 'static/file'
    
    # 安全检查，防止目录遍历
    if '..' in path:
        return jsonify({'error': 'Invalid path'}), 400
    
    # 获取文件列表
    items = get_file_tree(file_root, path if path != '/' else '')
    return jsonify(items)

@staticmethod # 静态方法，避免每次请求都创建实例
@app.before_request
def check_banned_ip():
    """拦截禁止访问的IP"""
    global data_ip
    user_ip = get_client_ip() # 获取用户IP地址
    banned_ips = data_ip.get('banned_ips', [])
    if check_ip(user_ip, banned_ips):
        return "<br><br><h3>您的IP已被禁止访问，如有疑问，请联系开发者。</h3>", 403
    
def get_client_ip():
    """
    获取客户端真实IP地址
    无论是否使用代理服务器，都尝试获取最可靠的客户端IP
    """
    # 首先检查常见的代理相关头部
    if request.headers.get('X-Forwarded-For'):
        # X-Forwarded-For格式: client_ip, proxy1_ip, proxy2_ip...
        # 最左侧的是原始客户端IP
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        if ip and ip != 'unknown':
            # app.logger.info(f"Got IP from X-Forwarded-For: {ip}")
            return ip
    
    # 检查X-Real-IP头部
    if request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
        if ip and ip != 'unknown':
            # app.logger.info(f"Got IP from X-Real-IP: {ip}")
            return ip
    
    # 检查其他可能的代理头部
    for header in ['X-Client-IP', 'X-ProxyUser-Ip', 'CF-Connecting-IP', 'True-Client-IP']:
        if request.headers.get(header):
            ip = request.headers.get(header)
            if ip and ip != 'unknown':
                # app.logger.info(f"Got IP from {header}: {ip}")
                return ip
    
    # 最后使用REMOTE_ADDR作为兜底方案
    ip = request.remote_addr or 'unknown'
    # app.logger.info(f"Using REMOTE_ADDR: {ip}")
    return ip

class Notice:
    @app.route('/notice')
    def notice_page():
        """公告页面"""
        return render_template('notice.html')

    @app.route('/notice/api', methods=['POST', 'GET'])
    def notice():
        global notice
        action = request.args.get('action')
        
        if action == 'get':
            notice = Notice.load_notice()
            # 直接返回公告列表，确保是JSON格式
            return jsonify(notice)
            
        # 对于POST请求，处理添加和编辑操作
        if request.method == 'POST':
            global data_ip
            try:
                data = request.get_json()
            except Exception as e:
                return jsonify({"success": False, "message": "Failed to parse request data."})
            
            limit_ips = data_ip.get('禁止编辑公告', [])
            if check_ip(get_client_ip(),limit_ips):
                return jsonify({"success": False, "message": "您的IP被禁止发布或编辑公告"})
            
            if action == 'add':
                if data is None:
                    return jsonify({"success": False, "message": "No notice content provided."})
                
                # 确保必需字段存在
                required_fields = ['id', 'title', 'author', 'content', 'date']
                for field in required_fields:
                    if field not in data or not data[field]:
                        return jsonify({"success": False, "message": f"Missing required field: {field}"})
                
                notice = Notice.load_notice()
                notice.append(data)
                Notice.save_notice(notice)
                log_operation(operation='添加公告', details=data, ip_address=get_client_ip())
                return jsonify({"success": True, "message": "Notice added successfully."})
                
            if action == 'edit':
                if data is None:
                    return jsonify({"success": False, "message": "No notice content provided."})             
                notice = Notice.load_notice()
                for i, item in enumerate(notice):
                    if data.get('id') == item.get('id'):
                        old_item = notice[i] # 保存旧数据以供日志记录
                        notice[i] = data
                        Notice.save_notice(notice)
                        data = {'old': old_item, 'new': data} # 记录修改前后的数据
                        log_operation(operation='编辑公告', details=data, ip_address=get_client_ip())
                        return jsonify({"success": True, "message": "Notice edited successfully."})
                return jsonify({"success": False, "message": "Notice not found."})
                
        return jsonify({"success": False, "message": "Invalid action or method."})
    
    def load_notice():
        if os.path.exists(NOTICE_FILE):
            with open(NOTICE_FILE, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return []
        return []

    def save_notice(notices):
        with open(NOTICE_FILE, 'w', encoding='utf-8') as f:
            json.dump(notices, f, ensure_ascii=False, indent=2)
            app.logger.info(f"公告保存成功！内容：{notices}")
        
class Homework:
    '''
    def __init__(self, subject, content, labels, deadline):
        self.subject = subject
        self.content = content
        self.labels = labels
        self.deadline = deadline
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    '''
    @app.route('/homework')
    def view_homework():
        # 每次访问时都重新加载数据，确保获取最新数据
        submissions = load_submissions()
        labels = Label.load_labels()
        subjects = Subject.load_subjects()  # 添加这行
        
        # 按学科分组作业
        grouped_submissions = {}
        for submission in submissions:
            subject = submission['subject']
            if subject not in grouped_submissions:
                grouped_submissions[subject] = []
            grouped_submissions[subject].append(submission)
        
        return render_template('homework.html', submissions=grouped_submissions, labels=labels, subjects=subjects)  # 添加 subjects
    
    @app.route('/api/homework')
    def api_homework():
        # API端点，返回JSON格式的作业数据
        submissions = load_submissions()
        labels = Label.load_labels()
        
        # 按学科分组作业
        grouped_submissions = {}
        for submission in submissions:
            subject = submission['subject']
            if subject not in grouped_submissions:
                grouped_submissions[subject] = []
            grouped_submissions[subject].append(submission)
        
        return jsonify({"submissions": grouped_submissions, "labels": labels})

    @app.route('/api/subjects')
    def api_subjects():
        # API端点，返回JSON格式的学科顺序数据
        subjects = Subject.load_subjects()
        # 按order字段排序
        subjects.sort(key=lambda x: x.get('order', 999))
        # 返回完整的学科对象，包含常用词等信息
        return jsonify(subjects)

    @app.route('/homework/publish', methods=['GET', 'POST'])
    def homework_publish():
        # 每次访问时都重新加载标签，确保获取最新数据
        labels = Label.load_labels()
        subjects = Subject.load_subjects()
        
        if request.method == 'POST':
            # 检查是否是 AJAX 请求
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            # 检查是否是返回修改操作
            return_to_edit = request.form.get('return_to_edit')
            if return_to_edit:
                # 将表单数据保存到session
                session['publish_subject'] = request.form.get('subject')
                session['publish_content'] = request.form.get('content')
                session['publish_label_ids'] = [int(x) for x in request.form.getlist('label_ids')]
                session['publish_deadline'] = request.form.get('deadline')
                # 重定向到发布页面，不清除session数据
                return redirect(url_for('homework_publish'))
            
            # 检查是否是确认操作
            confirm = request.form.get('confirm')
            
            # 获取表单数据
            subject = request.form.get('subject')
            content = request.form.get('content')
            label_ids = request.form.getlist('label_ids')  # 获取多选值
            deadline = request.form.get('deadline')
            
            # 基本验证
            errors = []
            if not subject:
                errors.append("请选择学科")
            if not content or len(content.strip()) < 2:
                errors.append("内容至少需要2个字符")
            
            if errors:
                if is_ajax:
                    return jsonify({'success': False, 'message': ' '.join(errors)})
                for error in errors:
                    flash(error, 'error')
            else:
                # 处理标签
                selected_labels = []
                selected_label_ids = []
                for label_id in label_ids:
                    label_obj = next((label for label in labels if label["id"] == int(label_id)), None)
                    if label_obj:
                        selected_labels.append(label_obj["name"])
                        selected_label_ids.append(int(label_id))
                
                # 如果没有选择标签，则添加"未知标签"
                if not selected_labels:
                    unknown_label = next((label for label in labels if label["name"] == "未知标签"), None)
                    if unknown_label:
                        selected_labels.append(unknown_label["name"])
                        selected_label_ids.append(unknown_label["id"])
                
                # 如果未确认，则显示确认页面
                if not confirm and not is_ajax:
                    confirm_data = {
                        'subject': subject,
                        'content': content,
                        'labels': selected_labels,
                        'deadline': deadline if deadline else '无截止日期'
                    }
                    # 将表单数据保存到session
                    session['publish_subject'] = subject
                    session['publish_content'] = content
                    session['publish_label_ids'] = [int(x) for x in label_ids]
                    session['publish_deadline'] = deadline
                    return render_template('homework_publish.html', 
                                        now=datetime.now(), 
                                        tomorrow=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
                                        labels=labels,
                                        subjects=subjects,
                                        confirm_data=confirm_data)
                
                # 确认后执行添加操作
                # 加载最新的数据
                submissions = load_submissions()
                
                # 保存提交的数据，使用下一个可用ID而不是数组长度+1
                next_id = max([s['id'] for s in submissions], default=0) + 1
                submission = {
                    'id': next_id,
                    'subject': subject,
                    'content': content,
                    'labels': selected_labels,
                    'label_ids': selected_label_ids,
                    'deadline': deadline if deadline else '',
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                submissions.append(submission)
                save_submissions(submissions)
                
                # 清除session中的发布数据
                session.pop('publish_subject', None)
                session.pop('publish_content', None)
                session.pop('publish_label_ids', None)
                session.pop('publish_deadline', None)
                
                # 记录日志
                log_operation("添加作业", {
                    "id": next_id,
                    "subject": subject,
                    "content": content,
                    "labels": selected_labels,
                    "deadline": deadline if deadline else '无截止日期'
                }, get_client_ip())
                
                if is_ajax:
                    return jsonify({'success': True, 'message': '作业布置成功！'})
                
                flash('作业布置成功！', 'success')
                return redirect(url_for('view_submissions'))
        else:
            # GET请求时清除session中的发布数据
            session.pop('publish_subject', None)
            session.pop('publish_content', None)
            session.pop('publish_label_ids', None)
            session.pop('publish_deadline', None)
        
        # 每次访问GET请求时都重新加载标签
        labels = Label.load_labels()
        subjects = Subject.load_subjects()
        return render_template('homework_publish.html', 
                            now=datetime.now(), 
                            tomorrow=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
                            labels=labels,
                            subjects=subjects)

    @app.route('/homework/edit/<int:homework_id>', methods=['GET', 'POST'])
    def edit_homework(homework_id):
        # 加载数据
        submissions = load_submissions()
        labels = Label.load_labels()
        subjects = Subject.load_subjects()
        
        # 查找要编辑的作业
        homework = next((s for s in submissions if s['id'] == homework_id), None)
        if not homework:
            flash('作业未找到！', 'error')
            return redirect(url_for('view_submissions'))
        
        if request.method == 'POST':
            # 检查是否是返回修改操作
            return_to_edit = request.form.get('return_to_edit')
            if return_to_edit:
                # 将表单数据保存到session
                session['edit_subject_' + str(homework_id)] = request.form.get('subject')
                session['edit_content_' + str(homework_id)] = request.form.get('content')
                session['edit_label_ids_' + str(homework_id)] = [int(x) for x in request.form.getlist('label_ids')]
                session['edit_deadline_' + str(homework_id)] = request.form.get('deadline')
                # 重定向到编辑页面，不清除session数据
                return redirect(url_for('edit_homework', homework_id=homework_id))
            
            # 检查是否是确认操作
            confirm = request.form.get('confirm')
            
            # 获取表单数据
            subject = request.form.get('subject')
            content = request.form.get('content')
            label_ids = request.form.getlist('label_ids')
            deadline = request.form.get('deadline')
            
            # 基本验证
            errors = []
            if not subject:
                errors.append("请选择学科")
            if not content or len(content.strip()) < 2:
                errors.append("内容至少需要2个字符")
            '''
            if not deadline:
                errors.append("请选择截止日期")
            '''

            if errors:
                for error in errors:
                    flash(error, 'error')
            else:
                # 处理标签
                selected_labels = []
                selected_label_ids = []
                for label_id in label_ids:
                    label_obj = next((label for label in labels if label["id"] == int(label_id)), None)
                    if label_obj:
                        selected_labels.append(label_obj["name"])
                        selected_label_ids.append(int(label_id))
                
                # 如果没有选择标签，则添加"未知标签"
                if not selected_labels:
                    unknown_label = next((label for label in labels if label["name"] == "未知标签"), None)
                    if unknown_label:
                        selected_labels.append(unknown_label["name"])
                        selected_label_ids.append(unknown_label["id"])
                
                # 如果未确认，则显示确认页面
                if not confirm:
                    updated_homework = {
                        'id': homework_id,
                        'subject': subject,
                        'content': content,
                        'labels': selected_labels,
                        'deadline': deadline if deadline else '',
                        'timestamp': homework['timestamp']
                    }
                    # 将表单数据保存到session
                    session['edit_subject_' + str(homework_id)] = subject
                    session['edit_content_' + str(homework_id)] = content
                    session['edit_label_ids_' + str(homework_id)] = [int(x) for x in label_ids]
                    session['edit_deadline_' + str(homework_id)] = deadline
                    return render_template('homework_edit.html', 
                                         homework=updated_homework, 
                                         labels=labels,
                                         subjects=subjects,
                                         now=datetime.now(),
                                         confirm=True)
                
                # 确认后执行更新操作
                # 重新加载数据以防并发修改
                submissions = load_submissions()
                homework = next((s for s in submissions if s['id'] == homework_id), None)
                if not homework:
                    flash('作业未找到！可能已被其他用户删除。', 'error')
                    return redirect(url_for('view_submissions'))
                
                # 更新作业数据
                homework['subject'] = subject
                homework['content'] = content
                homework['labels'] = selected_labels
                homework['label_ids'] = selected_label_ids
                homework['deadline'] = deadline if deadline else ''
                # 更新时间戳为当前时间（编辑时间）
                homework['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 保存更新后的数据
                save_submissions(submissions)
                
                # 清除session中的编辑数据
                session.pop('edit_subject_' + str(homework_id), None)
                session.pop('edit_content_' + str(homework_id), None)
                session.pop('edit_label_ids_' + str(homework_id), None)
                session.pop('edit_deadline_' + str(homework_id), None)
                
                # 记录日志
                log_operation("编辑作业", {
                    "id": homework_id,
                    "subject": subject,
                    "content": content,
                    "labels": selected_labels,
                    "deadline": deadline if deadline else '无截止日期'
                }, get_client_ip())
                
                flash('作业更新成功！', 'success')
                return redirect(url_for('view_submissions'))
        else:
            # 检查是否是从确认页面返回取消编辑（即使用session中的临时数据）
            use_session_data = request.args.get('from_confirm') == '1'
            
            if use_session_data:
                # 准备编辑数据，优先使用session中的数据
                subject = session.get('edit_subject_' + str(homework_id), homework['subject'])
                content = session.get('edit_content_' + str(homework_id), homework['content'])
                label_ids = session.get('edit_label_ids_' + str(homework_id), None)
                deadline = session.get('edit_deadline_' + str(homework_id), homework['deadline'])

                # 处理标签
                if label_ids is not None:
                    selected_labels = [label['name'] for label in labels if label['id'] in label_ids]
                else:
                    selected_labels = homework['labels']
            else:
                # 使用最新的数据，忽略session中的旧数据
                subject = homework['subject']
                content = homework['content']
                selected_labels = homework['labels']
                deadline = homework['deadline']
                # 清除可能存在的session数据
                session.pop('edit_subject_' + str(homework_id), None)
                session.pop('edit_content_' + str(homework_id), None)
                session.pop('edit_label_ids_' + str(homework_id), None)
                session.pop('edit_deadline_' + str(homework_id), None)

            # 构造临时作业对象
            temp_homework = {
                'id': homework_id,
                'subject': subject,
                'content': content,
                'labels': selected_labels,
                'deadline': deadline if deadline else '',
                'timestamp': homework['timestamp']
            }

            return render_template('homework_edit.html', 
                                 homework=temp_homework, 
                                 labels=labels, 
                                 subjects=subjects,
                                 now=datetime.now())
    
    @app.route('/homework/delete/<int:homework_id>', methods=['POST'])
    def delete_homework(homework_id):
        # 加载数据
        submissions = load_submissions()
        
        # 查找要删除的作业
        homework = next((s for s in submissions if s['id'] == homework_id), None)
        if not homework:
            # 检查是否是 AJAX 请求
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '作业未找到！'}), 404
            flash('作业未找到！', 'error')
            return redirect(url_for('view_submissions'))
        
        # 检查是否是确认操作
        confirm = request.form.get('confirm')
        
        # 如果未确认，则显示确认页面
        if not confirm:
            return render_template('homework_edit.html', homework=homework, labels=Label.load_labels(), now=datetime.now(), delete_confirm=True)
        
        # 确认后执行删除操作
        # 从列表中删除作业
        submissions = [s for s in submissions if s['id'] != homework_id]
        
        # 不再重新编号ID以保持连续性，避免编辑过程中的ID不一致问题
        # 保存更新后的数据
        save_submissions(submissions)
        
        # 记录日志
        log_operation("删除作业", {
            "id": homework_id,
            "subject": homework['subject'],
            "content": homework['content'],
            "labels": homework['labels'],
            "deadline": homework['deadline']
        }, get_client_ip())
        
        # 检查是否是 AJAX 请求
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': '作业删除成功！'})
        
        flash('作业删除成功！', 'success')
        return redirect(url_for('view_submissions'))

    @app.route('/homework/delete_confirm/<int:homework_id>')
    def delete_homework_confirm(homework_id):
        # 加载数据
        submissions = load_submissions()
        
        # 查找要删除的作业
        homework = next((s for s in submissions if s['id'] == homework_id), None)
        if not homework:
            flash('作业未找到！', 'error')
            return redirect(url_for('view_submissions'))
        
        return render_template('homework_delete.html', homework=homework)

    @app.route('/homework/clear/all', methods=['POST'])
    def clear_all_homework():
        password = request.form.get('password')
        
        if password == Config.clear_password:
            submissions = load_submissions()
            save_submissions([])
            log_operation("清空所有作业", submissions, get_client_ip())
            return jsonify({'success': True, 'message': '所有作业已清空！'})
        else:
            return jsonify({'success': False, 'message': '密码错误！'}), 401

@app.route('/submissions')
def view_submissions():
    # 每次访问时都重新加载数据，确保获取最新数据
    submissions = load_submissions()
    labels = Label.load_labels()
    return render_template('submissions.html', submissions=submissions, labels=labels)

class Label:
    def load_labels():
        """从JSON文件加载标签数据"""
        global default_labels, LABELS_FILE, save_labels
        if os.path.exists(LABELS_FILE):
            with open(LABELS_FILE, 'r', encoding='utf-8') as f:
                try:
                    labels = json.load(f)
                    # 确保所有标签都有颜色属性
                    for label in labels:
                        if 'color' not in label:
                            if label['name'] == '未知标签':
                                label['color'] = '#808080'  # 灰色
                            else:
                                label['color'] = '#3498db'  # 默认蓝色
                    return labels
                except json.JSONDecodeError:
                    pass
        save_labels(default_labels)
        return default_labels
    @app.route('/label/edit', methods=['GET', 'POST'])
    def edit_labels():
        # 每次访问时都重新加载标签，确保获取最新数据
        labels = Label.load_labels()
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'add':
                # 添加新标签
                new_label_name = request.form.get('new_label_name')
                new_label_color = request.form.get('new_label_color', '#3498db')  # 默认蓝色
                if new_label_name:
                    # 检查标签是否已存在
                    if not any(label["name"] == new_label_name for label in labels):
                        # 生成新的ID（避免与现有ID冲突）
                        new_id = max([label["id"] for label in labels]) + 1 if labels else 1
                        labels.append({"id": new_id, "name": new_label_name, "color": new_label_color})
                        save_labels(labels)
                        flash('标签添加成功！', 'success')
                    else:
                        flash('标签已存在！', 'error')
                else:
                    flash('标签名称不能为空！', 'error')
                    
            elif action == 'update':
                # 更新标签名称
                label_id = int(request.form.get('label_id'))
                new_name = request.form.get('new_name')
                new_color = request.form.get('new_color')
                
                # 查找"未知标签"，防止被修改
                unknown_label = next((label for label in labels if label["name"] == "未知标签"), None)
                
                if label_id and new_name:
                    # 确保不修改"未知标签"
                    if unknown_label and unknown_label["id"] == label_id:
                        flash('无法修改"未知标签"！', 'error')
                    else:
                        # 更新标签名称
                        for label in labels:
                            if label["id"] == label_id:
                                label["name"] = new_name
                                label["color"] = new_color
                                break
                        save_labels(labels)
                        flash('标签更新成功！', 'success')
                else:
                    flash('无效的标签ID或名称！', 'error')
            elif action == 'delete':
                # 删除标签
                label_id = int(request.form.get('label_id'))
                
                # 查找"未知标签"，防止被删除
                unknown_label = next((label for label in labels if label["name"] == "未知标签"), None)
                
                # 确保不删除"未知标签"
                if unknown_label and unknown_label["id"] == label_id:
                    flash('无法删除"未知标签"！', 'error')
                else:
                    # 删除标签
                    labels = [label for label in labels if label["id"] != label_id]
                    save_labels(labels)
                    flash('标签删除成功！', 'success')
            
            # 重新加载标签
            labels = Label.load_labels()
        
        # 重新加载标签
        labels = Label.load_labels()
        return render_template('label_edit.html', labels=labels)


class Subject:
    @staticmethod
    def load_subjects():
        """从JSON文件加载科目数据"""
        if os.path.exists(SUBJECTS_FILE):
            with open(SUBJECTS_FILE, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    pass
        
        # 默认科目列表
        default_subjects = [
            {"id": 1, "name": "语文", "order": 1, "common_words": []},
            {"id": 2, "name": "数学", "order": 2, "common_words": []},
            {"id": 3, "name": "英语", "order": 3, "common_words": []},
            {"id": 4, "name": "物理", "order": 4, "common_words": []},
            {"id": 5, "name": "化学", "order": 5, "common_words": []},
            {"id": 6, "name": "生物学", "order": 6, "common_words": []},
            {"id": 7, "name": "历史", "order": 7, "common_words": []},
            {"id": 8, "name": "地理", "order": 8, "common_words": []},
            {"id": 9, "name": "思想政治", "order": 9, "common_words": []},
            {"id": 10, "name": "其他", "order": 10, "common_words": []}
        ]
        
        Subject.save_subjects(default_subjects)
        return default_subjects
    
    @staticmethod
    def save_subjects(subjects):
        """将科目数据保存到JSON文件"""
        with open(SUBJECTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(subjects, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def get_common_words_by_subject(subject_name):
        """根据科目名称获取常用词"""
        subjects = Subject.load_subjects()
        subject = next((s for s in subjects if s["name"] == subject_name), None)
        if subject:
            return subject.get("common_words", [])
        return []
    
    @staticmethod
    def get_all_common_words_list():
        """获取所有通用常用词列表（用于模板渲染）"""
        # 检查是否存在专门的通用词文件
        GLOBAL_WORDS_FILE = os.path.join(Config.DATA_DIR, 'global_words.json')
        if os.path.exists(GLOBAL_WORDS_FILE):
            with open(GLOBAL_WORDS_FILE, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    pass
        
        # 如果没有单独的通用词文件，则回退到原来的逻辑
        subjects = Subject.load_subjects()
        all_words = []
        for subject in subjects:
            all_words.extend(subject.get("common_words", []))
        # 只返回通用词（出现在多个科目中的词）
        word_count = {}
        for word in all_words:
            word_count[word] = word_count.get(word, 0) + 1
        return [word for word, count in word_count.items() if count > 1]
    
    @staticmethod
    @app.route('/api/global_words', methods=['GET'])
    def get_all_common_words():
        """获取所有通用常用词（不属于特定科目的词）"""
        words = Subject.get_all_common_words_list()
        return jsonify(words)

    @staticmethod
    def save_global_common_words(words):
        """保存全局常用词到独立文件"""
        GLOBAL_WORDS_FILE = os.path.join(Config.DATA_DIR, 'global_words.json')
        with open(GLOBAL_WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(words, f, ensure_ascii=False, indent=2)

    @app.route('/subjects', methods=['GET', 'POST'])
    def manage_subjects():
        """管理科目和常用词"""
        subjects = Subject.load_subjects()
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'update_order':
                # 更新科目顺序
                subject_orders = request.form.getlist('subject_order')
                subject_names = request.form.getlist('subject_name')
                
                for i, (name, order) in enumerate(zip(subject_names, subject_orders)):
                    for subject in subjects:
                        if subject['name'] == name:
                            subject['order'] = int(order)
                            break
                
                # 根据order字段排序
                subjects.sort(key=lambda x: x['order'])
                Subject.save_subjects(subjects)
                flash('科目顺序更新成功！', 'success')
                
            elif action == 'add_word':
                # 添加常用词
                subject_id_str = request.form.get('subject_id')
                subject_id = int(subject_id_str) if subject_id_str else None
                new_word = request.form.get('new_word')
                is_global = request.form.get('is_global') == 'true'
                
                if new_word:
                    # 如果是全局词，添加到全局词列表
                    if is_global:
                        global_words = Subject.get_all_common_words_list()
                        if new_word not in global_words:
                            global_words.append(new_word)
                            Subject.save_global_common_words(global_words)
                        flash(f'通用常用词"{new_word}"添加成功！', 'success')
                    else:
                        # 否则添加到指定科目
                        if subject_id is not None:
                            for subject in subjects:
                                if subject['id'] == subject_id:
                                    if 'common_words' not in subject:
                                        subject['common_words'] = []
                                    if new_word not in subject['common_words']:
                                        subject['common_words'].append(new_word)
                                    break
                            Subject.save_subjects(subjects)
                            flash(f'常用词"{new_word}"添加成功！', 'success')
                        else:
                            flash('请选择科目！', 'error')
                else:
                    flash('常用词不能为空！', 'error')
                    
            elif action == 'remove_word':
                # 删除常用词
                subject_id_str = request.form.get('subject_id')
                subject_id = int(subject_id_str) if subject_id_str else None
                word_to_remove = request.form.get('word')
                is_global = request.form.get('is_global') == 'true'
                
                # 如果是全局词，从全局词列表中删除
                if is_global:
                    global_words = Subject.get_all_common_words_list()
                    if word_to_remove in global_words:
                        global_words.remove(word_to_remove)
                        Subject.save_global_common_words(global_words)
                    flash(f'通用常用词"{word_to_remove}"删除成功！', 'success')
                else:
                    # 否则只从指定科目中删除
                    if subject_id is not None:
                        for subject in subjects:
                            if subject['id'] == subject_id:
                                if 'common_words' in subject and word_to_remove in subject['common_words']:
                                    subject['common_words'].remove(word_to_remove)
                                break
                        Subject.save_subjects(subjects)
                        flash(f'常用词"{word_to_remove}"删除成功！', 'success')
                    else:
                        flash('请选择科目！', 'error')
            # 重新加载数据
            subjects = Subject.load_subjects()
        return render_template('subjects.html', subjects=subjects)

class Fun:
    @app.route('/902504')
    def fun_index():
        """Fun类主页，需要身份验证"""
        # 检查是否已通过身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            # 未验证，重定向到验证页面
            return redirect(url_for('fun_auth'))
        
        # 验证通过，显示主页
        return render_template('fun_index.html', name=name, student_id=student_id)
    
    @app.route('/902504/auth', methods=['GET', 'POST'])
    def fun_auth():
        """身份验证页面"""
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            student_id = request.form.get('student_id', '').strip()
            password = request.form.get('password', '').strip()
            
            print(f"调试信息 - 输入姓名: '{name}', 学号: '{student_id}', 密码: '{password}'")
            print(f"调试信息 - students_data类型: {type(students_data)}")
            print(f"调试信息 - students_data内容: {students_data}")
            
            # 确保students_data是字典
            if not isinstance(students_data, dict):
                print(f"错误: students_data不是字典，而是{type(students_data)}")
                flash('系统配置错误，请联系管理员', 'error')
                return render_template('fun_auth.html', name=name, student_id=student_id)
            
            # 验证用户信息
            authenticated = False
            matched_name = None
            matched_id = None
            
            # 方法1: 直接键值匹配
            if name and name in students_data:
                expected_id = str(students_data[name]).strip()
                input_id = student_id.strip()
                print(f"调试信息 - 直接匹配: 期望学号='{expected_id}', 输入学号='{input_id}'")
                
                if input_id == expected_id:
                    # 验证密码
                    if student_id in password_data:
                        # 使用存储的密码验证
                        if password_data[student_id] == password:
                            authenticated = True
                            matched_name = name
                            matched_id = expected_id
                            print(f"调试信息 - 密码验证成功（自定义密码）")
                        else:
                            flash('密码不正确！', 'error')
                            print(f"调试信息 - 密码错误 预期密码='{password_data[student_id]}', 输入密码='{password}'")
                            return render_template('fun_auth.html', name=name, student_id=student_id)
                    else:
                        # 使用默认密码验证
                        if password == get_default_password():
                            authenticated = True
                            matched_name = name
                            matched_id = expected_id
                            print(f"调试信息 - 密码验证成功（默认密码）")
                        else:
                            flash('密码不正确！', 'error')
                            print(f"调试信息 - 密码错误 预期密码（默认密码）='{get_default_password()}', 输入密码='{password}'")
                            return render_template('fun_auth.html', name=name, student_id=student_id)
            
            # 方法2: 如果直接匹配失败，尝试遍历所有项进行模糊匹配
            if not authenticated and students_data:
                print(f"调试信息 - 开始模糊匹配")
                for stored_name, stored_id in students_data.items():
                    stored_name_clean = str(stored_name).strip()
                    stored_id_clean = str(stored_id).strip()
                    input_name_clean = name.strip()
                    input_id_clean = student_id.strip()
                    
                    print(f"调试信息 - 比较: '{input_name_clean}' vs '{stored_name_clean}', '{input_id_clean}' vs '{stored_id_clean}'")
                    
                    # 比较去除空格后的值
                    if (input_name_clean == stored_name_clean and 
                        input_id_clean == stored_id_clean):
                        # 验证密码
                        if stored_id_clean in password_data:
                            # 使用存储的密码验证
                            if password_data[stored_id_clean] == password:
                                authenticated = True
                                matched_name = stored_name_clean
                                matched_id = stored_id_clean
                                print(f"调试信息 - 模糊匹配成功: {matched_name}")
                                break
                            else:
                                flash('密码不正确！', 'error')
                                return render_template('fun_auth.html', name=name, student_id=student_id)
                        else:
                            # 使用默认密码验证
                            if password == get_default_password():
                                authenticated = True
                                matched_name = stored_name_clean
                                matched_id = stored_id_clean
                                print(f"调试信息 - 模糊匹配成功: {matched_name}")
                                break
                            else:
                                flash('密码不正确！', 'error')
                                return render_template('fun_auth.html', name=name, student_id=student_id)
            
            if authenticated:
                # 验证成功
                ip_address = get_client_ip()
                
                # 记录登录日志
                log_login(matched_name, matched_id, ip_address)
                
                # 创建响应并设置cookie
                response = make_response(redirect(url_for('fun_index')))
                # 设置cookie，有效期30天
                response.set_cookie('fun_name', matched_name, max_age=30*24*60*60)
                response.set_cookie('fun_student_id', matched_id, max_age=30*24*60*60)
                
                flash('身份验证成功！', 'success')
                return response
            else:
                # 验证失败
                print(f"调试信息 - 验证失败")
                flash('姓名、学号或密码不正确，请重试！', 'error')
                # 保留表单数据以便重新输入
                return render_template('fun_auth.html', name=name, student_id=student_id)
        
        return render_template('fun_auth.html')
    
    @app.route('/902504/password', methods=['GET', 'POST'])
    def fun_password():
        """密码设置页面"""
        # 检查身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            return redirect(url_for('fun_auth'))
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'set_password':
                current_password = request.form.get('current_password', '').strip()
                new_password = request.form.get('new_password', '').strip()
                confirm_password = request.form.get('confirm_password', '').strip()
                
                # 验证当前密码
                if student_id in password_data:
                    # 使用自定义密码验证
                    if password_data[student_id] != current_password:
                        flash('当前密码不正确！', 'error')
                        return render_template('fun_password.html', name=name, student_id=student_id)
                else:
                    # 使用默认密码验证
                    if current_password != get_default_password():
                        flash('当前密码不正确！', 'error')
                        return render_template('fun_password.html', name=name, student_id=student_id)
                
                # 验证新密码
                is_valid, message = validate_password(new_password)
                if not is_valid:
                    flash(message, 'error')
                    return render_template('fun_password.html', name=name, student_id=student_id)
                
                # 确认密码匹配
                if new_password != confirm_password:
                    flash('新密码和确认密码不匹配！', 'error')
                    return render_template('fun_password.html', name=name, student_id=student_id)
                
                # 保存新密码
                password_data[student_id] = new_password
                save_password_data()
                
                flash('密码设置成功！', 'success')
                return redirect(url_for('fun_index'))
            
            elif action == 'reset_password':
                # 重置密码（删除自定义密码，使用默认密码）
                if student_id in password_data:
                    del password_data[student_id]
                    save_password_data()
                    flash('密码已重置为默认密码！', 'success')
                else:
                    flash('您当前使用的是默认密码，无需重置！', 'info')
                return redirect(url_for('fun_index'))
        
        return render_template('fun_password.html', name=name, student_id=student_id)
    
    @app.route('/902504/logout')
    def fun_logout():
        """退出登录"""
        response = make_response(redirect(url_for('fun_auth')))
        response.set_cookie('fun_name', '', expires=0)
        response.set_cookie('fun_student_id', '', expires=0)
        flash('已退出登录', 'success')
        return response
    
    @app.route('/902504/submit', methods=['GET', 'POST'])
    def fun_submit():
        """提交表单页面"""
        # 检查身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            return redirect(url_for('fun_auth'))
        
        if request.method == 'POST':
            content = request.form.get('content')
            anonymous = request.form.get('anonymous') == 'on'
            
            # 检查提交频率限制
            limit_check = check_submit_limit(name, student_id)
            
            if limit_check['within_30s']:
                flash('提交过于频繁，请间隔至少30秒再提交！', 'error')
            elif limit_check['within_24h']:
                flash('您今天的提交次数已达上限（15次）！', 'error')
            # 验证内容
            elif not content or len(content.strip()) == 0:
                flash('内容不能为空！', 'error')
            elif len(content) > 1600:
                flash('内容不能超过1600字符！', 'error')
            else:
                # 记录输入
                ip_address = get_client_ip()
                log_input(content, name, student_id, ip_address, anonymous)
                
                flash('提交成功！', 'success')
                return redirect(url_for('fun_view'))
        
        return render_template('fun_submit.html', name=name, student_id=student_id)
    
    @app.route('/902504/view')
    def fun_view():
        """查看所有提交的页面"""
        # 检查身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            return redirect(url_for('fun_auth'))
        
        # 加载所有输入
        inputs = load_inputs()

        for input in inputs:
            if 'anonymous' in input and input['anonymous'] == True:
                input['name'] = '匿名'
                input['student_id'] = '匿名'
        
        # 按时间倒序排列
        inputs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # 获取客户端IP地址
        client_ip = get_client_ip()
        
        return render_template('fun_view.html', inputs=inputs, name=name, request=request, client_ip=client_ip)

    @app.route('/902504/delete_input', methods=['POST'])
    def fun_delete_input():
        """删除提交内容"""
        # 检查身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            return redirect(url_for('fun_auth'))
        
        # 获取要删除的条目信息
        timestamp = request.form.get('timestamp')
        content = request.form.get('content')
        
        if not timestamp or not content:
            flash('无效的请求', 'error')
            return redirect(url_for('fun_view'))
        
        # 加载所有输入
        inputs = load_inputs()
        
        # 获取客户端IP地址
        client_ip = get_client_ip()
        
        # 查找并删除匹配的条目
        original_length = len(inputs)
        
        # 检查权限：是否是发布者或管理员IP
        new_inputs = []
        deleted = False
        for input_entry in inputs:
            # 检查是否匹配要删除的条目
            if (input_entry['timestamp'] == timestamp and 
                input_entry['content'] == content):
                # 检查权限：发布者或管理员
                if (input_entry['student_id'] == student_id or 
                    client_ip == '127.0.0.1' or 
                    client_ip in data_ip.get('admin_ips', [])):
                    deleted = True
                    # 不添加到new_inputs中，实现删除
                else:
                    # 没有权限，保留条目
                    new_inputs.append(input_entry)
            else:
                # 不是要删除的条目，保留
                new_inputs.append(input_entry)
        
        # 如果没有删除任何条目，说明权限不足
        if not deleted:
            flash('删除失败，可能是权限不足', 'error')
            return redirect(url_for('fun_view'))
        
        # 保存更新后的数据
        with open(INPUT_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_inputs, f, ensure_ascii=False, indent=2)
        
        # 记录删除操作日志
        log_operation("删除提交内容", {
            "timestamp": timestamp,
            "content": content
        }, client_ip)
        
        flash('删除成功', 'success')
        return redirect(url_for('fun_view'))
    
    @app.route('/902504/debug/students')
    def debug_students():
        """调试页面，显示学生数据"""
        return jsonify({
            "students_data": students_data,
            "data_type": type(students_data).__name__,
            "is_dict": isinstance(students_data, dict),
            "keys": list(students_data.keys()) if isinstance(students_data, dict) else "N/A"
        })
    
    @app.route('/902504/upload', methods=['GET', 'POST'])
    def upload():
        """文件上传页面"""
        # 检查身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            return redirect(url_for('fun_auth'))
        
        if request.method == 'POST':
            # 处理文件上传
            if 'file' not in request.files:
                flash('没有选择文件', 'error')
                return render_template('upload.html', name=name, student_id=student_id)
            
            file = request.files['file']
            
            # 检查文件名
            if file.filename == '':
                flash('没有选择文件', 'error')
                return render_template('upload.html', name=name, student_id=student_id)
            
            if file:
                # 获取上传路径
                upload_path = request.form.get('upload_path', '').strip()
                # 清理路径，防止目录遍历攻击
                if upload_path:
                    # 移除路径开头和结尾的斜杠
                    upload_path = upload_path.strip('/')
                    # 防止目录遍历攻击
                    if '..' in upload_path:
                        flash('上传路径不合法', 'error')
                        return render_template('upload.html', name=name, student_id=student_id)
                    upload_path += '/'
                
                # 确保upload_path以斜杠结尾或为空
                if upload_path and not upload_path.endswith('/'):
                    upload_path += '/'
                
                # 构建完整的保存路径
                save_directory = os.path.join('static', upload_path.strip('/'))
                
                # 确保目录存在
                os.makedirs(save_directory, exist_ok=True)
                
                # 获取文件大小
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                # 检查文件大小限制 (1.5GB)
                max_file_size = 1.5 * 1024 * 1024 * 1024  # 1.5GB in bytes
                if file_size > max_file_size:
                    flash('文件大小超过1.5GB限制', 'error')
                    return render_template('upload.html', name=name, student_id=student_id)
                
                # 检查用户配额 (每月2GB)
                quota_check, quota_message = check_user_upload_quota(name, student_id, file_size)
                if not quota_check:
                    flash(quota_message, 'error')
                    return render_template('upload.html', name=name, student_id=student_id)
                
                # 生成安全的文件名
                filename = file.filename
                if '.' in filename:
                    # 保留文件扩展名
                    name_part, ext = os.path.splitext(filename)
                    # 生成安全的文件名
                    safe_name = re.sub(r'[^\w\-_\.]', '_', name_part)
                    filename = safe_name + ext
                else:
                    # 没有扩展名的情况
                    filename = re.sub(r'[^\w\-_]', '_', filename)
                
                # 构建完整文件路径
                file_path = os.path.join(save_directory, filename)
                
                # 处理文件名冲突
                counter = 1
                original_filename = filename
                while os.path.exists(file_path):
                    name_part, ext = os.path.splitext(original_filename)
                    filename = f"{name_part}_{counter}{ext}"
                    file_path = os.path.join(save_directory, filename)
                    counter += 1
                
                try:
                    # 保存文件
                    file.save(file_path)
                    
                    # 记录上传日志
                    client_ip = get_client_ip()
                    log_file_upload(
                        filename=filename,
                        upload_path=upload_path,
                        file_size=file_size,
                        user_name=name,
                        user_id=student_id,
                        ip_address=client_ip
                    )
                    
                    # 计算文件大小显示格式
                    if file_size < 1024:
                        size_str = f"{file_size} bytes"
                    elif file_size < 1024 * 1024:
                        size_str = f"{file_size / 1024:.2f} KB"
                    elif file_size < 1024 * 1024 * 1024:
                        size_str = f"{file_size / (1024 * 1024):.2f} MB"
                    else:
                        size_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB"
                    
                    flash(f'文件上传成功！文件名: {filename}, 大小: {size_str}', 'success')
                except Exception as e:
                    flash(f'文件上传失败: {str(e)}', 'error')
        
        return render_template('upload.html', name=name, student_id=student_id)
    
class AI:
    # 保存对话历史的文件路径
    CHAT_HISTORY_FILE = os.path.join(Config.DATA_DIR, 'chat_history.json')
    PUBLIC_CHAT_HISTORY_FILE = os.path.join(Config.DATA_DIR, 'public_chat_history.json')
    # 保存系统提示词的文件路径
    SYSTEM_PROMPT_FILE = os.path.join(Config.DATA_DIR, 'system_prompt.txt')
    PUBLIC_SYSTEM_PROMPT_FILE = os.path.join(Config.DATA_DIR, 'public_system_prompt.txt')
    # 保存预设问答的文件路径
    QA_PROMPT_FILE = os.path.join(Config.DATA_DIR, 'qa_prompt.json')
    
    @staticmethod
    def get_default_system_prompt():
        """获取默认系统提示词"""
        return "你是一个乐于助人的AI助手。请用友好、专业的语气回答用户的问题。"
    
    @staticmethod
    def load_system_prompt(is_public=False):
        """加载系统提示词"""
        prompt_file = AI.PUBLIC_SYSTEM_PROMPT_FILE if is_public else AI.SYSTEM_PROMPT_FILE
        if os.path.exists(prompt_file):
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        else:
            default_prompt = AI.get_default_system_prompt()
            AI.save_system_prompt(default_prompt, is_public)
            return default_prompt
    
    @staticmethod
    def save_system_prompt(prompt, is_public=False):
        """保存系统提示词"""
        prompt_file = AI.PUBLIC_SYSTEM_PROMPT_FILE if is_public else AI.SYSTEM_PROMPT_FILE
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
    
    @staticmethod
    def load_qa_prompt():
        """加载预设问答"""
        if os.path.exists(AI.QA_PROMPT_FILE):
            with open(AI.QA_PROMPT_FILE, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return []
        return []
    
    @staticmethod
    def save_qa_prompt(qa_list):
        """保存预设问答"""
        with open(AI.QA_PROMPT_FILE, 'w', encoding='utf-8') as f:
            json.dump(qa_list, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_chat_history(user_identifier, max_history=100, is_public=False):
        """加载用户的聊天历史"""
        history_file = AI.PUBLIC_CHAT_HISTORY_FILE if is_public else AI.CHAT_HISTORY_FILE
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                try:
                    if is_public:
                        return json.load(f)[-max_history:]  # 公共聊天直接返回最新消息
                    else:
                        all_history = json.load(f)
                        return all_history.get(user_identifier, [])[-max_history:]
                except json.JSONDecodeError:
                    return []
        return []
    
    @staticmethod
    def save_chat_message(user_identifier, role, content, is_public=False, name=None):
        """保存聊天消息"""
        history_file = AI.PUBLIC_CHAT_HISTORY_FILE if is_public else AI.CHAT_HISTORY_FILE
        
        # 加载现有历史
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                try:
                    if is_public:
                        all_history = json.load(f)
                    else:
                        all_history = json.load(f)
                except json.JSONDecodeError:
                    all_history = [] if is_public else {}
        else:
            all_history = [] if is_public else {}
        
        if is_public:
            # 公共聊天历史
            message = {
                'user_identifier': user_identifier,
                'name': name,
                'role': role,
                'content': content,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            all_history.append(message)
            
            # 限制公共历史记录长度（保留最近200条）
            if len(all_history) > 200:
                all_history = all_history[-200:]
        else:
            # 私人聊天历史
            if user_identifier not in all_history:
                all_history[user_identifier] = []
            
            message = {
                'role': role,
                'content': content,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            all_history[user_identifier].append(message)
            
            # 限制私人历史记录长度（保留最近50条）
            if len(all_history[user_identifier]) > 50:
                all_history[user_identifier] = all_history[user_identifier][-50:]
        
        # 保存回文件
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(all_history, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def clear_chat_history(user_identifier, is_public=False):
        """清空用户的聊天历史"""
        history_file = AI.PUBLIC_CHAT_HISTORY_FILE if is_public else AI.CHAT_HISTORY_FILE
        
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                try:
                    if is_public:
                        # 公共聊天只能清空自己的消息
                        all_history = json.load(f)
                        all_history = [msg for msg in all_history if msg.get('user_identifier') != user_identifier]
                    else:
                        all_history = json.load(f)
                        if user_identifier in all_history:
                            all_history[user_identifier] = []
                    
                    with open(history_file, 'w', encoding='utf-8') as fw:
                        json.dump(all_history, fw, ensure_ascii=False, indent=2)
                    return True
                except json.JSONDecodeError:
                    return False
        return False
    
    @staticmethod
    def clear_public_chat_history(user_identifier):
        """清空公共聊天历史（所有人的消息）"""
        if os.path.exists(AI.PUBLIC_CHAT_HISTORY_FILE):
            try:
                # 记录清空前的历史内容（用于日志）
                with open(AI.PUBLIC_CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    old_history = json.load(f)
                
                # 清空公共聊天历史文件
                with open(AI.PUBLIC_CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                
                return True, old_history
            except json.JSONDecodeError:
                return False, []
        return False, []

    @staticmethod
    def check_private_chat_limit(user_identifier):
        """检查私人聊天发送频率限制（每分钟最多3条）"""
        private_history = AI.load_chat_history(user_identifier, max_history=50, is_public=False)
        
        # 获取当前时间和1分钟前的时间
        now = datetime.now()
        past_1_minute = now - timedelta(minutes=1)
        
        # 统计用户1分钟内的消息数量
        user_messages_1min = []
        
        for message in private_history:
            if message.get('role') == 'user':
                try:
                    entry_time = datetime.strptime(message['timestamp'], "%Y-%m-%d %H:%M:%S")
                    if entry_time >= past_1_minute:
                        user_messages_1min.append(message)
                except ValueError:
                    continue
        
        return len(user_messages_1min) >= 3  # 1分钟内是否已有3条消息

    @staticmethod
    def check_public_chat_limit(user_identifier):
        """检查公共聊天发送频率限制（非AI消息每2分钟最多1条）"""
        public_history = AI.load_chat_history(user_identifier, max_history=300, is_public=True)
        
        # 获取当前时间和2分钟前的时间
        now = datetime.now()
        past_2_minutes = now - timedelta(minutes=2)
        
        # 统计用户2分钟内的非AI消息数量
        user_messages_2min = []
        
        for message in public_history:
            if (message.get('user_identifier') == user_identifier and 
                message.get('role') == 'user' and 
                not message.get('content', '').strip().startswith('@ai')):
                try:
                    entry_time = datetime.strptime(message['timestamp'], "%Y-%m-%d %H:%M:%S")
                    if entry_time >= past_2_minutes:
                        user_messages_2min.append(message)
                except ValueError:
                    continue
        
        return len(user_messages_2min) >= 1  # 2分钟内是否已有非AI消息

    @staticmethod
    def openai_stream(model="deepseek-v3.2-exp", messages=[]):
        """流式调用OpenAI API"""
        try:
            client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                extra_body={"enable_thinking": False},
            )
            
            for chunk in completion:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            # 捕获API调用异常，返回友好的错误信息
            error_message = f"抱歉，AI服务暂时不可用。错误信息：{str(e)}"
            yield error_message

    @staticmethod
    def openai(model="deepseek-v3.2-exp", messages=[]):
        """非流式调用OpenAI API"""
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        completion = client.chat.completions.create(
            model=model, 
            messages=messages,
        )
        return completion.choices[0].message.content

    @app.route('/902504/ai-chat', methods=['GET', 'POST'])
    def ai_chat():
        """AI聊天页面 - 个人对话"""
        # 检查身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            return redirect(url_for('fun_auth'))
        
        user_identifier = f"{name}_{student_id}"
        chat_type = request.args.get('type', 'private')  # private 或 public
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'clear_history':
                # 清空聊天历史
                is_public = request.form.get('chat_type') == 'public'
                
                if is_public:
                    # 清空公共聊天历史（所有人的消息）
                    success, old_history = AI.clear_public_chat_history(user_identifier)
                    if success:
                        # 记录清空公共聊天历史的操作日志
                        log_operation("清空公共聊天历史", {
                            "user_identifier": user_identifier,
                            "cleared_messages_count": len(old_history),
                            "old_messages_preview": [{"user": msg.get('name', '未知'), "content": msg.get('content', '')[:50]} for msg in old_history[:5]]  # 只记录前5条作为预览
                        }, get_client_ip())
                        flash('公共聊天历史已清空！', 'success')
                    else:
                        flash('清空公共聊天历史失败！', 'error')
                else:
                    # 清空私人聊天历史（原有逻辑）
                    if AI.clear_chat_history(user_identifier, is_public=False):
                        flash('您的私人聊天历史已清空！', 'success')
                    else:
                        flash('清空聊天历史失败！', 'error')
                
                return redirect(url_for('ai_chat', type=chat_type))
            
            elif action == 'send_message':
                user_message = request.form.get('message', '').strip()
                is_public = request.form.get('chat_type') == 'public'
                
                if not user_message:
                    flash('消息不能为空！', 'error')
                    return redirect(url_for('ai_chat', type=chat_type))
                
                # 保存用户消息
                AI.save_chat_message(user_identifier, 'user', user_message, is_public=is_public, name=name)
                
                # 修复：私人对话直接调用AI，不需要@ai前缀
                if not is_public or user_message.startswith('@ai'):
                    # 私人聊天频率限制检查
                    if not is_public and AI.check_private_chat_limit(user_identifier):
                        flash('私人对话中，每分钟最多只能发送3条消息！', 'error')
                        return redirect(url_for('ai_chat', type=chat_type))
                    
                    # 公共聊天频率限制检查（仅对非@ai消息）
                    if is_public and not user_message.startswith('@ai') and AI.check_public_chat_limit(user_identifier):
                        flash('公共聊天中，非AI消息每2分钟只能发送一条！', 'error')
                        return redirect(url_for('ai_chat', type=chat_type))
                    
                    # 准备对话历史
                    chat_history = AI.load_chat_history(user_identifier, max_history=20, is_public=is_public)
                    system_prompt = AI.load_system_prompt(is_public=is_public)
                    
                    # 构建消息列表
                    messages = [{'role': 'system', 'content': system_prompt}]
                    
                    # 添加问答式prompt（仅公共聊天）
                    if is_public:
                        qa_prompt = AI.load_qa_prompt()
                        if qa_prompt:
                            qa_context = "以下是一些预设问答，请参考这些信息来回答问题：\n\n"
                            for qa in qa_prompt:
                                if 'question' in qa and 'answer' in qa:
                                    qa_context += f"问：{qa['question']}\n答：{qa['answer']}\n\n"
                            messages[0]['content'] += "\n\n" + qa_context
                    
                    # 添加上下文消息
                    if is_public:
                        # 公共聊天包含最近的15条消息作为上下文
                        recent_messages = chat_history[-15:]
                        for msg in recent_messages:
                            content = msg['content']
                            if msg['role'] == 'user' and msg.get('name'):
                                content = f"{msg['name']}说：{content}"
                            messages.append({'role': msg['role'], 'content': content})
                    else:
                        # 私人聊天包含完整历史
                        for msg in chat_history:
                            messages.append({'role': msg['role'], 'content': msg['content']})
                    
                    # 添加当前用户消息
                    current_user_content = user_message
                    if is_public:
                        current_user_content = f"{name}说：{user_message}"
                    messages.append({'role': 'user', 'content': current_user_content})
                    
                    # 如果是AJAX请求，返回流式响应
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        def generate():
                            full_response = ""
                            for chunk in AI.openai_stream(messages=messages):
                                full_response += chunk
                                yield f"data: {json.dumps({'content': chunk})}\n\n"
                            
                            # 保存AI回复
                            AI.save_chat_message(user_identifier, 'assistant', full_response, 
                                            is_public=is_public, name="AI助手")
                            yield "data: [DONE]\n\n"
                        
                        return Response(generate(), mimetype='text/plain')
                    
                    # 非AJAX请求，使用普通模式
                    try:
                        ai_response = AI.openai(messages=messages)
                        AI.save_chat_message(user_identifier, 'assistant', ai_response, 
                                        is_public=is_public, name="AI助手")
                    except Exception as e:
                        flash(f'AI服务暂时不可用: {str(e)}', 'error')
                else:
                    # 对于公共聊天的非@ai消息，不调用AI，但已经保存了消息
                    flash('消息已发送！', 'success')
                    return redirect(url_for('ai_chat', type=chat_type))
        
        # 加载聊天历史
        is_public = chat_type == 'public'
        chat_history = AI.load_chat_history(user_identifier, max_history=50, is_public=is_public)
        
        return render_template('ai_chat.html', 
                            chat_history=chat_history,
                            name=name,
                            student_id=student_id,
                            chat_type=chat_type)

    @app.route('/902504/ai-settings', methods=['GET', 'POST'])
    def ai_settings():
        """AI设置页面"""
        # 检查身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            return redirect(url_for('fun_auth'))
        
        user_identifier = f"{name}_{student_id}"
        ip_address = get_client_ip()  # 获取客户端IP
        
        # 从cookie获取密码验证状态
        public_prompt_see_cookie = request.cookies.get('ai_public_prompt_see')
        qa_see_cookie = request.cookies.get('ai_qa_see')
        
        public_prompt_visible = public_prompt_see_cookie == Config.AI_SYSTEM_SEE_PASSWORD
        qa_visible = qa_see_cookie == Config.AI_SYSTEM_SEE_PASSWORD
        
        response = None
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'verify_password':
                target = request.form.get('target')
                password = request.form.get('password')
                
                resp = make_response(redirect(url_for('ai_settings')))
                
                # 根据目标检查相应密码
                if target == 'public_prompt' and password == Config.AI_SYSTEM_SEE_PASSWORD:
                    resp.set_cookie('ai_public_prompt_see', password, max_age=30*60)  # 30分钟有效
                    flash('密码验证成功！现在可以查看和编辑公共提示词。', 'success')
                elif target == 'qa' and password == Config.AI_SYSTEM_SEE_PASSWORD:
                    resp.set_cookie('ai_qa_see', password, max_age=30*60)  # 30分钟有效
                    flash('密码验证成功！现在可以管理预设问答。', 'success')
                else:
                    flash('密码错误！', 'error')
                
                return resp
                    
            elif action == 'update_prompt':
                new_prompt = request.form.get('system_prompt', '').strip()
                prompt_type = request.form.get('prompt_type', 'private')  # private 或 public
                
                # 对于公共提示词的处理
                if prompt_type == 'public':
                    # 检查是否已验证查看权限
                    if not public_prompt_visible:
                        flash('您没有权限编辑公共提示词，请先验证查看密码。', 'error')
                    else:
                        # 需要额外验证编辑密码
                        edit_password = request.form.get('edit_password')
                        if edit_password != Config.AI_SYSTEM_EDIT_PASSWORD:
                            flash('编辑公共提示词需要输入编辑密码！', 'error')
                            # 显示编辑密码输入框
                            response = make_response(AI.render_template_with_data())
                            response.set_cookie('show_edit_password_prompt', 'true')
                            return response
                        else:
                            old_prompt = AI.load_system_prompt(is_public=(prompt_type == 'public'))
                            AI.save_system_prompt(new_prompt, is_public=(prompt_type == 'public'))
                            
                            # 记录提示词更新日志
                            log_prompt_operation(
                                operation=f"update_{prompt_type}_prompt",
                                details={
                                    "old_prompt": old_prompt,
                                    "new_prompt": new_prompt,
                                    "prompt_type": prompt_type
                                },
                                user_identifier=user_identifier,
                                ip_address=ip_address
                            )
                            
                            flash('公共系统提示词更新成功！', 'success')
                elif new_prompt:
                    old_prompt = AI.load_system_prompt(is_public=(prompt_type == 'public'))
                    AI.save_system_prompt(new_prompt, is_public=(prompt_type == 'public'))
                    
                    # 记录提示词更新日志
                    log_prompt_operation(
                        operation=f"update_{prompt_type}_prompt",
                        details={
                            "old_prompt": old_prompt,
                            "new_prompt": new_prompt,
                            "prompt_type": prompt_type
                        },
                        user_identifier=user_identifier,
                        ip_address=ip_address
                    )
                    
                    flash('系统提示词更新成功！', 'success')
                else:
                    flash('提示词不能为空！', 'error')
            
            elif action == 'reset_prompt':
                prompt_type = request.form.get('prompt_type', 'private')
                
                # 对于公共提示词的处理
                if prompt_type == 'public':
                    # 检查是否已验证查看权限
                    if not public_prompt_visible:
                        flash('您没有权限重置公共提示词，请先验证查看密码。', 'error')
                    else:
                        # 需要额外验证编辑密码
                        edit_password = request.form.get('edit_password')
                        if edit_password != Config.AI_SYSTEM_EDIT_PASSWORD:
                            flash('重置公共提示词需要输入编辑密码！', 'error')
                            # 显示编辑密码输入框
                            response = make_response(AI.render_template_with_data())
                            response.set_cookie('show_edit_password_prompt', 'true')
                            return response
                        else:
                            old_prompt = AI.load_system_prompt(is_public=(prompt_type == 'public'))
                            default_prompt = AI.get_default_system_prompt()
                            AI.save_system_prompt(default_prompt, is_public=(prompt_type == 'public'))
                            
                            # 记录提示词重置日志
                            log_prompt_operation(
                                operation=f"reset_{prompt_type}_prompt",
                                details={
                                    "old_prompt": old_prompt,
                                    "new_prompt": default_prompt,
                                    "prompt_type": prompt_type
                                },
                                user_identifier=user_identifier,
                                ip_address=ip_address
                            )
                            
                            flash('公共系统提示词已重置为默认值！', 'success')
                else:
                    old_prompt = AI.load_system_prompt(is_public=(prompt_type == 'public'))
                    default_prompt = AI.get_default_system_prompt()
                    AI.save_system_prompt(default_prompt, is_public=(prompt_type == 'public'))
                    
                    # 记录提示词重置日志
                    log_prompt_operation(
                        operation=f"reset_{prompt_type}_prompt",
                        details={
                            "old_prompt": old_prompt,
                            "new_prompt": default_prompt,
                            "prompt_type": prompt_type
                        },
                        user_identifier=user_identifier,
                        ip_address=ip_address
                    )
                    
                    flash('系统提示词已重置为默认值！', 'success')
            
            elif action == 'clear_my_history':
                history_type = request.form.get('history_type', 'private')
                if history_type == 'public':
                    # 清空公共聊天历史（所有人的消息）
                    success, old_history = AI.clear_public_chat_history(user_identifier)
                    if success:
                        # 记录清空公共聊天历史的操作日志
                        log_operation("清空公共聊天历史", {
                            "user_identifier": user_identifier,
                            "cleared_messages_count": len(old_history),
                            "old_messages_preview": [{"user": msg.get('name', '未知'), "content": msg.get('content', '')[:50]} for msg in old_history[:5]]  # 只记录前5条作为预览
                        }, get_client_ip())
                        flash('公共聊天历史已清空！', 'success')
                    else:
                        flash('清空公共聊天历史失败！', 'error')
                else:
                    # 清空私人聊天历史
                    if AI.clear_chat_history(user_identifier, is_public=False):
                        flash('您的私人聊天历史已清空！', 'success')
                    else:
                        flash('清空聊天历史失败！', 'error')
            
            elif action == 'add_qa':
                # 添加预设问答
                if not qa_visible:
                    flash('您没有权限添加预设问答，请先验证查看密码。', 'error')
                else:
                    # 需要额外验证编辑密码
                    edit_password = request.form.get('edit_password')
                    if edit_password != Config.AI_SYSTEM_EDIT_PASSWORD:
                        flash('添加预设问答需要输入编辑密码！', 'error')
                        # 显示编辑密码输入框
                        response = make_response(AI.render_template_with_data())
                        response.set_cookie('show_edit_password_prompt', 'true')
                        return response
                    else:
                        question = request.form.get('qa_question', '').strip()
                        answer = request.form.get('qa_answer', '').strip()
                        if question and answer:
                            qa_list = AI.load_qa_prompt()
                            new_qa = {
                                'question': question,
                                'answer': answer,
                                'id': len(qa_list) + 1
                            }
                            qa_list.append(new_qa)
                            AI.save_qa_prompt(qa_list)
                            
                            # 记录预设问答添加日志
                            log_prompt_operation(
                                operation="add_qa",
                                details={
                                    "question": question,
                                    "answer": answer,
                                    "qa_id": new_qa['id']
                                },
                                user_identifier=user_identifier,
                                ip_address=ip_address
                            )
                            
                            flash('预设问答添加成功！', 'success')
                        else:
                            flash('问题和答案都不能为空！', 'error')
            
            elif action == 'delete_qa':
                # 删除预设问答
                if not qa_visible:
                    flash('您没有权限删除预设问答，请先验证查看密码。', 'error')
                else:
                    # 需要额外验证编辑密码
                    edit_password = request.form.get('edit_password')
                    if edit_password != Config.AI_SYSTEM_EDIT_PASSWORD:
                        flash('删除预设问答需要输入编辑密码！', 'error')
                        # 显示编辑密码输入框
                        response = make_response(AI.render_template_with_data())
                        response.set_cookie('show_edit_password_prompt', 'true')
                        return response
                    else:
                        qa_id = int(request.form.get('qa_id', 0))
                        if qa_id > 0:
                            qa_list = AI.load_qa_prompt()
                            # 找到要删除的QA记录详情
                            deleted_qa = None
                            for qa in qa_list:
                                if qa.get('id') == qa_id:
                                    deleted_qa = qa
                                    break
                            
                            qa_list = [qa for qa in qa_list if qa.get('id') != qa_id]
                            AI.save_qa_prompt(qa_list)
                            
                            # 记录预设问答删除日志
                            if deleted_qa:
                                log_prompt_operation(
                                    operation="delete_qa",
                                    details={
                                        "question": deleted_qa.get('question'),
                                        "answer": deleted_qa.get('answer'),
                                        "qa_id": qa_id
                                    },
                                    user_identifier=user_identifier,
                                    ip_address=ip_address
                                )
                            
                            flash('预设问答删除成功！', 'success')
        
        # 如果没有特殊的response，则正常渲染模板
        if response is None:
            response = make_response(AI.render_template_with_data(
                private_prompt=AI.load_system_prompt(is_public=False),
                public_prompt=AI.load_system_prompt(is_public=True),
                qa_list=AI.load_qa_prompt(),
                private_history=AI.load_chat_history(user_identifier, is_public=False),
                public_history=AI.load_chat_history(user_identifier, is_public=True),
                private_count=len(AI.load_chat_history(user_identifier, is_public=False)),
                public_count=len([msg for msg in AI.load_chat_history(user_identifier, is_public=True) if msg.get('user_identifier') == user_identifier]),
                name=name,
                student_id=student_id,
                public_prompt_visible=public_prompt_visible,
                qa_visible=qa_visible
            ))
        
        return response
    
    def render_template_with_data(**kwargs):
        """辅助函数，用于渲染模板并传递数据"""
        # 设置默认值
        defaults = {
            'private_prompt': AI.load_system_prompt(is_public=False),
            'public_prompt': AI.load_system_prompt(is_public=True),
            'qa_list': AI.load_qa_prompt(),
            'name': request.cookies.get('fun_name'),
            'student_id': request.cookies.get('fun_student_id')
        }
        
        # 计算动态默认值
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        user_identifier = f"{name}_{student_id}" if name and student_id else ""
        
        if user_identifier:
            defaults.update({
                'private_history': AI.load_chat_history(user_identifier, is_public=False),
                'public_history': AI.load_chat_history(user_identifier, is_public=True),
                'private_count': len(AI.load_chat_history(user_identifier, is_public=False)),
                'public_count': len([msg for msg in AI.load_chat_history(user_identifier, is_public=True) if msg.get('user_identifier') == user_identifier])
            })
        
        # 合并传入参数
        defaults.update(kwargs)
        
        # 处理可见性参数
        defaults.setdefault('public_prompt_visible', request.cookies.get('ai_public_prompt_see') == Config.AI_SYSTEM_SEE_PASSWORD)
        defaults.setdefault('qa_visible', request.cookies.get('ai_qa_see') == Config.AI_SYSTEM_SEE_PASSWORD)
        
        return render_template('ai_settings.html', **defaults)

homework = Homework()
label = Label()
subject = Subject()
fun = Fun()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=app.config.get('DEBUG', False), port=2025)