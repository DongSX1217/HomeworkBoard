import flask
from flask import Flask, render_template, request, flash, redirect, url_for, session
import base64, time, json, re, os, uuid, threading, requests, smtplib, sys
import http.client
from datetime import datetime, timedelta

app = Flask(__name__) # 创建 Flask 应用
app.secret_key = 'test_key'  # 生产环境中使用强密钥

@app.context_processor
def inject_subject_class():
    return dict(Subject=Subject)

# 确保data目录存在
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DATA_FILE = os.path.join(DATA_DIR, 'submissions.json')
LABELS_FILE = os.path.join(DATA_DIR, 'labels.json')
LOG_FILE = os.path.join(DATA_DIR, 'operation.log')
SUBJECTS_FILE = os.path.join(DATA_DIR, 'subjects.json')

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
        
        return {"submissions": grouped_submissions, "labels": labels}

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
                                         subjects=subjects,
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
        }, request.remote_addr)
        
        flash('作业删除成功！', 'success')
        return redirect(url_for('view_submissions'))

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
    def get_all_common_words():
        """获取所有通用常用词（不属于特定科目的词）"""
        subjects = Subject.load_subjects()
        all_words = []
        for subject in subjects:
            all_words.extend(subject.get("common_words", []))
        # 只返回通用词（出现在多个科目中的词）
        word_count = {}
        for word in all_words:
            word_count[word] = word_count.get(word, 0) + 1
        return [word for word, count in word_count.items() if count > 1]

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
                subject_id = int(request.form.get('subject_id'))
                new_word = request.form.get('new_word')
                is_global = request.form.get('is_global') == 'true'
                
                if new_word:
                    # 如果是全局词，添加到所有科目
                    if is_global:
                        for subject in subjects:
                            if 'common_words' not in subject:
                                subject['common_words'] = []
                            if new_word not in subject['common_words']:
                                subject['common_words'].append(new_word)
                        Subject.save_subjects(subjects)
                        flash(f'通用常用词"{new_word}"添加成功！', 'success')
                    else:
                        # 否则添加到指定科目
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
                    flash('常用词不能为空！', 'error')
                    
            elif action == 'remove_word':
                # 删除常用词
                subject_id = int(request.form.get('subject_id'))
                word_to_remove = request.form.get('word')
                is_global = request.form.get('is_global') == 'true'
                
                # 如果是全局词，从所有科目中删除
                if is_global:
                    for subject in subjects:
                        if 'common_words' in subject and word_to_remove in subject['common_words']:
                            subject['common_words'].remove(word_to_remove)
                    Subject.save_subjects(subjects)
                    flash(f'通用常用词"{word_to_remove}"删除成功！', 'success')
                else:
                    # 否则只从指定科目中删除
                    for subject in subjects:
                        if subject['id'] == subject_id:
                            if 'common_words' in subject and word_to_remove in subject['common_words']:
                                subject['common_words'].remove(word_to_remove)
                            break
                    Subject.save_subjects(subjects)
                    flash(f'常用词"{word_to_remove}"删除成功！', 'success')
            # 重新加载数据
            subjects = Subject.load_subjects()
        return render_template('subjects.html', subjects=subjects)


homework = Homework()
label = Label()
subject = Subject()
if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True,port=2025)