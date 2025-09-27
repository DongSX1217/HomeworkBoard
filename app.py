import flask
from flask import Flask, render_template, request, flash, redirect, url_for, session
import base64, time, json, re, os, uuid, threading, requests, smtplib, sys
import http.client
from datetime import datetime, timedelta

app = Flask(__name__) # 创建 Flask 应用
app.secret_key = 'test_key'  # 生产环境中使用强密钥

# 确保data目录存在
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DATA_FILE = os.path.join(DATA_DIR, 'submissions.json')
LABELS_FILE = os.path.join(DATA_DIR, 'labels.json')
LOG_FILE = os.path.join(DATA_DIR, 'operation.log')

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

def load_labels():
    """从JSON文件加载标签数据"""
    if os.path.exists(LABELS_FILE):
        with open(LABELS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    # 默认标签
    default_labels = [
        {"id": 1, "name": "课堂前由课代表/小组长检查"},
        {"id": 2, "name": "课堂前由授课教师检查"},
        {"id": 3, "name": "小组任务"},
        {"id": 4, "name": "自行核对答案"},
        {"id": 5, "name": "复习作业"},
        {"id": 6, "name": "预习作业"},
        {"id": 7, "name": "拓展任务"},
        {"id": 8, "name": "选做"},
        {"id": 9, "name": "教师布置"},
        {"id": 10, "name": "未知标签"}
    ]
    save_labels(default_labels)
    return default_labels

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

# 初始化数据
submissions = load_submissions()

@app.route('/')
def homepage():
    return render_template('home.html')

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
        labels = load_labels()
        
        # 按学科分组作业
        grouped_submissions = {}
        for submission in submissions:
            subject = submission['subject']
            if subject not in grouped_submissions:
                grouped_submissions[subject] = []
            grouped_submissions[subject].append(submission)
        
        return render_template('homework.html', submissions=grouped_submissions)
    
    @app.route('/api/homework')
    def api_homework():
        # API端点，返回JSON格式的作业数据
        submissions = load_submissions()
        
        # 按学科分组作业
        grouped_submissions = {}
        for submission in submissions:
            subject = submission['subject']
            if subject not in grouped_submissions:
                grouped_submissions[subject] = []
            grouped_submissions[subject].append(submission)
        
        return {"submissions": grouped_submissions}

    @app.route('/homework/publish', methods=['GET', 'POST'])
    def homework_publish():
        # 每次访问时都重新加载标签，确保获取最新数据
        labels = load_labels()
        
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
                for label_id in label_ids:
                    label_obj = next((label for label in labels if label["id"] == int(label_id)), None)
                    if label_obj:
                        selected_labels.append(label_obj["name"])
                
                # 如果没有选择标签，则添加"未知标签"
                if not selected_labels:
                    unknown_label = next((label for label in labels if label["name"] == "未知标签"), None)
                    if unknown_label:
                        selected_labels.append(unknown_label["name"])
                
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
                    "subject": subject,
                    "content": content,
                    "labels": selected_labels,
                    "deadline": deadline if deadline else '无截止日期'
                }, request.remote_addr)
                
                flash('作业布置成功！', 'success')
                return redirect(url_for('view_submissions'))
        else:
            # GET请求时清除session中的发布数据
            session.pop('publish_subject', None)
            session.pop('publish_content', None)
            session.pop('publish_label_ids', None)
            session.pop('publish_deadline', None)
        
        # 每次访问GET请求时都重新加载标签
        labels = load_labels()
        return render_template('homework_publish.html', 
                             now=datetime.now(), 
                             tomorrow=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
                             labels=labels)

    @app.route('/homework/edit/<int:homework_id>', methods=['GET', 'POST'])
    def edit_homework(homework_id):
        # 加载数据
        submissions = load_submissions()
        labels = load_labels()
        
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
                for label_id in label_ids:
                    label_obj = next((label for label in labels if label["id"] == int(label_id)), None)
                    if label_obj:
                        selected_labels.append(label_obj["name"])
                
                # 如果没有选择标签，则添加"未知标签"
                if not selected_labels:
                    unknown_label = next((label for label in labels if label["name"] == "未知标签"), None)
                    if unknown_label:
                        selected_labels.append(unknown_label["name"])
                
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
                                         now=datetime.now(),
                                         confirm=True)
                
                # 确认后执行更新操作
                # 更新作业数据
                homework['subject'] = subject
                homework['content'] = content
                homework['labels'] = selected_labels
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
                }, request.remote_addr)
                
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

            return render_template('homework_edit.html', homework=temp_homework, labels=labels, now=datetime.now())
    
    @app.route('/homework/delete/<int:homework_id>', methods=['POST'])
    def delete_homework(homework_id):
        # 加载数据
        submissions = load_submissions()
        
        # 查找要删除的作业
        homework = next((s for s in submissions if s['id'] == homework_id), None)
        if not homework:
            flash('作业未找到！', 'error')
            return redirect(url_for('view_submissions'))
        
        # 检查是否是确认操作
        confirm = request.form.get('confirm')
        
        # 如果未确认，则显示确认页面
        if not confirm:
            return render_template('homework_edit.html', homework=homework, labels=load_labels(), now=datetime.now(), delete_confirm=True)
        
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
        }, request.remote_addr)
        
        flash('作业删除成功！', 'success')
        return redirect(url_for('view_submissions'))

@app.route('/submissions')
def view_submissions():
    # 每次访问时都重新加载数据，确保获取最新数据
    submissions = load_submissions()
    labels = load_labels()
    return render_template('submissions.html', submissions=submissions, labels=labels)

class Label:
    @app.route('/label/edit', methods=['GET', 'POST'])
    def edit_labels():
        # 每次访问时都重新加载标签，确保获取最新数据
        labels = load_labels()
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'add':
                # 添加新标签
                new_label_name = request.form.get('new_label_name')
                if new_label_name:
                    # 检查标签是否已存在
                    if not any(label["name"] == new_label_name for label in labels):
                        # 生成新的ID（避免与现有ID冲突）
                        new_id = max([label["id"] for label in labels]) + 1 if labels else 1
                        labels.append({"id": new_id, "name": new_label_name})
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
            labels = load_labels()
        
        # 重新加载标签
        labels = load_labels()
        return render_template('label_edit.html', labels=labels)

homework = Homework()
label = Label()
if __name__ == '__main__':
    app.run(debug=True,port=2025)