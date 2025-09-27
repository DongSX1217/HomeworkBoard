import flask
from flask import Flask, render_template, request, redirect, url_for
import base64, time, json, re, os, uuid, threading, requests, smtplib, sys
import http.client

app = Flask(__name__) # 创建 Flask 应用

@app.route('/')
def homepage():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)