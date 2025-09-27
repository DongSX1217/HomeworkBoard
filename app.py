import flask
from flask import Flask, render_template, request, flash, redirect, url_for
import base64, time, json, re, os, uuid, threading, requests, smtplib, sys
import http.client
from datetime import datetime

app = Flask(__name__) # 创建 Flask 应用
app.secret_key = 'test_key'  # 生产环境中使用强密钥

# 确保data目录存在
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DATA_FILE = os.path.join(DATA_DIR, 'submissions.json')

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

# 初始化数据
submissions = load_submissions()

@app.route('/')
def homepage():
    return render_template('home.html')

@app.route('/input', methods=['GET', 'POST'])
def inputpage():
    if request.method == 'POST':
        # 获取表单数据
        subject = request.form.get('subject')
        content = request.form.get('content')
        labels = request.form.getlist('labels')  # 获取多选值
        deadline = request.form.get('deadline')
        
        # 基本验证
        errors = []
        if not subject:
            errors.append("请选择学科")
        if not content or len(content.strip()) < 5:
            errors.append("内容至少需要5个字符")
        if not deadline:
            errors.append("请选择截止日期")
        
        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            # 加载最新的数据
            global submissions
            submissions = load_submissions()
            
            # 保存提交的数据
            submission = {
                'id': len(submissions) + 1,
                'subject': subject,
                'content': content,
                'labels': labels,
                'deadline': deadline,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            submissions.append(submission)
            save_submissions(submissions)
            flash('表单提交成功！', 'success')
            return redirect(url_for('view_submissions'))
    
    return render_template('input.html', now=datetime.now())

@app.route('/submissions')
def view_submissions():
    # 每次访问时都重新加载数据，确保获取最新数据
    submissions = load_submissions()
    return render_template('submissions.html', submissions=submissions)

if __name__ == '__main__':
    app.run(debug=True,port=2025)