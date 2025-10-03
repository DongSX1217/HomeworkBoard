import flask
from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify, make_response, Response
import base64, time, json, re, os, uuid, threading, requests, smtplib, sys
import http.client
from datetime import datetime, timedelta
from openai import OpenAI

app = Flask(__name__) # 创建 Flask 应用
app.secret_key = 'test_key'  # 生产环境中使用强密钥

@app.context_processor
def inject_subject_class(): # 注入Subject类到模板
    return dict(Subject=Subject) # 返回一个包含Subject类的字典

# 确保data目录存在
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DATA_FILE = os.path.join(DATA_DIR, 'submissions.json')
LABELS_FILE = os.path.join(DATA_DIR, 'labels.json')
LOG_FILE = os.path.join(DATA_DIR, 'operation.log')
SUBJECTS_FILE = os.path.join(DATA_DIR, 'subjects.json')
IP_FILE = os.path.join(DATA_DIR, 'ips.json')
STUDENTS_FILE = os.path.join(DATA_DIR, 'students.json')
LOGIN_LOG_FILE = os.path.join(DATA_DIR, 'login.log')
INPUT_LOG_FILE = os.path.join(DATA_DIR, 'input.log')
PASSWORD_FILE = os.path.join(DATA_DIR, 'password.json')

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
        except json.JSONDecodeError:
            password_data = {}
else:
    # 如果没有密码文件，创建一个空的
    password_data = {}
    with open(PASSWORD_FILE, 'w', encoding='utf-8') as f:
        json.dump(password_data, f, ensure_ascii=False, indent=4)

@app.route('/')
def homepage():
    return render_template('home.html')

@staticmethod # 静态方法，避免每次请求都创建实例
@app.before_request
def check_banned_ip():
    """拦截禁止访问的IP"""
    global data_ip
    user_ip = get_client_ip() # 获取用户IP地址
    banned_ips = data_ip.get('banned_ips', [])
    if user_ip in banned_ips:
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
        
        # 按学科分组作业
        grouped_submissions = {}
        for submission in submissions:
            subject = submission['subject']
            if subject not in grouped_submissions:
                grouped_submissions[subject] = []
            grouped_submissions[subject].append(submission)
        
        return render_template('homework.html', submissions=grouped_submissions, labels=labels)
    
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
        # 返回学科名称列表，按排序顺序
        return jsonify([subject['name'] for subject in subjects])

    @app.route('/homework/publish', methods=['GET', 'POST'])
    def homework_publish():
        # 每次访问时都重新加载标签，确保获取最新数据
        labels = Label.load_labels()
        subjects = Subject.load_subjects()
        
        if request.method == 'POST':
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
            if not content or len(content.strip()) < 5:
                errors.append("内容至少需要5个字符")
            # 移除了必须填写截止日期的要求
            
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
                
                # 保存提交的数据
                submission = {
                    'id': len(submissions) + 1,
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
                '''
                session.pop('publish_subject', None)
                session.pop('publish_content', None)
                session.pop('publish_label_ids', None)
                session.pop('publish_deadline', None)'''
                
                # 记录日志
                log_operation("添加作业", {
                    "subject": subject,
                    "content": content,
                    "labels": selected_labels,
                    "deadline": deadline if deadline else '无截止日期'
                }, get_client_ip())
                
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
            if not content or len(content.strip()) < 5:
                errors.append("内容至少需要5个字符")
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
                
                # 清除session中的编辑数据，'
                '''
                session.pop('edit_subject_' + str(homework_id), None)
                session.pop('edit_content_' + str(homework_id), None)
                session.pop('edit_label_ids_' + str(homework_id), None)
                session.pop('edit_deadline_' + str(homework_id), None)'''
                
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
        
        # 重新编号ID以保持连续性
        for i, submission in enumerate(submissions):
            submission['id'] = i + 1
        
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
        GLOBAL_WORDS_FILE = os.path.join(DATA_DIR, 'global_words.json')
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
        GLOBAL_WORDS_FILE = os.path.join(DATA_DIR, 'global_words.json')
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
        
        return render_template('fun_view.html', inputs=inputs, name=name)
    
    @app.route('/902504/debug/students')
    def debug_students():
        """调试页面，显示学生数据"""
        return jsonify({
            "students_data": students_data,
            "data_type": type(students_data).__name__,
            "is_dict": isinstance(students_data, dict),
            "keys": list(students_data.keys()) if isinstance(students_data, dict) else "N/A"
        })
    
class AI:
    # 保存对话历史的文件路径
    CHAT_HISTORY_FILE = os.path.join(DATA_DIR, 'chat_history.json')
    # 保存系统提示词的文件路径
    SYSTEM_PROMPT_FILE = os.path.join(DATA_DIR, 'system_prompt.txt')
    
    @staticmethod
    def get_default_system_prompt():
        """获取默认系统提示词"""
        return "你是一个乐于助人的AI助手。请用友好、专业的语气回答用户的问题。"
    
    @staticmethod
    def load_system_prompt():
        """加载系统提示词"""
        if os.path.exists(AI.SYSTEM_PROMPT_FILE):
            with open(AI.SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        else:
            default_prompt = AI.get_default_system_prompt()
            AI.save_system_prompt(default_prompt)
            return default_prompt
    
    @staticmethod
    def save_system_prompt(prompt):
        """保存系统提示词"""
        with open(AI.SYSTEM_PROMPT_FILE, 'w', encoding='utf-8') as f:
            f.write(prompt)
    
    @staticmethod
    def load_chat_history(user_identifier, max_history=10):
        """加载用户的聊天历史"""
        if os.path.exists(AI.CHAT_HISTORY_FILE):
            with open(AI.CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                try:
                    all_history = json.load(f)
                    return all_history.get(user_identifier, [])[-max_history:]
                except json.JSONDecodeError:
                    return []
        return []
    
    @staticmethod
    def save_chat_message(user_identifier, role, content):
        """保存聊天消息"""
        # 加载现有历史
        if os.path.exists(AI.CHAT_HISTORY_FILE):
            with open(AI.CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                try:
                    all_history = json.load(f)
                except json.JSONDecodeError:
                    all_history = {}
        else:
            all_history = {}
        
        # 确保用户有历史记录
        if user_identifier not in all_history:
            all_history[user_identifier] = []
        
        # 添加新消息
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        all_history[user_identifier].append(message)
        
        # 限制历史记录长度（保留最近50条）
        if len(all_history[user_identifier]) > 50:
            all_history[user_identifier] = all_history[user_identifier][-50:]
        
        # 保存回文件
        with open(AI.CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_history, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def clear_chat_history(user_identifier):
        """清空用户的聊天历史"""
        if os.path.exists(AI.CHAT_HISTORY_FILE):
            with open(AI.CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                try:
                    all_history = json.load(f)
                    if user_identifier in all_history:
                        all_history[user_identifier] = []
                    with open(AI.CHAT_HISTORY_FILE, 'w', encoding='utf-8') as fw:
                        json.dump(all_history, fw, ensure_ascii=False, indent=2)
                    return True
                except json.JSONDecodeError:
                    return False
        return False

    @staticmethod
    def openai_stream(model="qwen3-max", messages=[]):
        """流式调用OpenAI API"""
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )
        
        for chunk in completion:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    @staticmethod
    def openai(model="qwen3-max", messages=[]):
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
        """AI聊天页面"""
        # 检查身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            return redirect(url_for('fun_auth'))
        
        user_identifier = f"{name}_{student_id}"
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'clear_history':
                # 清空聊天历史
                AI.clear_chat_history(user_identifier)
                flash('聊天历史已清空！', 'success')
                return redirect(url_for('ai_chat'))
            
            elif action == 'send_message':
                user_message = request.form.get('message', '').strip()
                if not user_message:
                    flash('消息不能为空！', 'error')
                    return redirect(url_for('ai_chat'))
                
                # 保存用户消息
                AI.save_chat_message(user_identifier, 'user', user_message)
                
                # 准备对话历史
                chat_history = AI.load_chat_history(user_identifier)
                system_prompt = AI.load_system_prompt()
                
                # 构建消息列表
                messages = [{'role': 'system', 'content': system_prompt}]
                messages.extend(chat_history)
                messages.append({'role': 'user', 'content': user_message})
                
                # 如果是AJAX请求，返回流式响应
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    def generate():
                        full_response = ""
                        for chunk in AI.openai_stream(messages=messages):
                            full_response += chunk
                            yield f"data: {json.dumps({'content': chunk})}\n\n"
                        
                        # 保存AI回复
                        AI.save_chat_message(user_identifier, 'assistant', full_response)
                        yield "data: [DONE]\n\n"
                    
                    return Response(generate(), mimetype='text/plain')
                
                # 非AJAX请求，使用普通模式
                try:
                    ai_response = AI.openai(messages=messages)
                    AI.save_chat_message(user_identifier, 'assistant', ai_response)
                except Exception as e:
                    flash(f'AI服务暂时不可用: {str(e)}', 'error')
        
        # 加载聊天历史
        chat_history = AI.load_chat_history(user_identifier)
        return render_template('ai_chat.html', 
                             chat_history=chat_history,
                             name=name,
                             student_id=student_id)

    @app.route('/902504/ai-settings', methods=['GET', 'POST'])
    def ai_settings():
        """AI设置页面"""
        # 检查身份验证
        name = request.cookies.get('fun_name')
        student_id = request.cookies.get('fun_student_id')
        
        if not name or not student_id:
            return redirect(url_for('fun_auth'))
        
        user_identifier = f"{name}_{student_id}"
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'update_prompt':
                new_prompt = request.form.get('system_prompt', '').strip()
                if new_prompt:
                    AI.save_system_prompt(new_prompt)
                    flash('系统提示词更新成功！', 'success')
                else:
                    flash('提示词不能为空！', 'error')
            
            elif action == 'reset_prompt':
                default_prompt = AI.get_default_system_prompt()
                AI.save_system_prompt(default_prompt)
                flash('系统提示词已重置为默认值！', 'success')
            
            elif action == 'clear_my_history':
                if AI.clear_chat_history(user_identifier):
                    flash('您的聊天历史已清空！', 'success')
                else:
                    flash('清空聊天历史失败！', 'error')
        
        # 加载当前系统提示词和用户聊天历史统计
        system_prompt = AI.load_system_prompt()
        chat_history = AI.load_chat_history(user_identifier)
        history_count = len(chat_history)
        
        return render_template('ai_settings.html',
                             system_prompt=system_prompt,
                             history_count=history_count,
                             name=name,
                             student_id=student_id)

homework = Homework()
label = Label()
subject = Subject()
fun = Fun()
if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True,port=2025)