from flask import Flask, render_template, request, redirect, session, flash, send_from_directory, jsonify
import os
import json
import random
import string
import time
import uuid
import ctypes
import smtplib
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'suiyecloud2026'
app.config['MAX_CONTENT_LENGTH'] = 5368709120
UPLOAD = 'uploads'
AVATAR = 'avatars'
os.makedirs(UPLOAD, exist_ok=True)
os.makedirs(AVATAR, exist_ok=True)

dll = None
try:
    dll = ctypes.CDLL('./speed_io.dll')
    dll.fastCopy.restype = ctypes.c_bool
    dll.isOver5GB.restype = ctypes.c_bool
except:
    pass

users = {}
shares = {}
codes = {}
graph_codes = {}

try:
    with open('users.json','r',encoding='utf-8') as f:
        users = json.load(f)
except:
    pass

def save_users():
    with open('users.json','w',encoding='utf-8') as f:
        json.dump(users,f,ensure_ascii=False)

def send_code(to_email):
    code = ''.join(random.choices(string.digits, k=6))
    codes[to_email] = code
    msg = MIMEText(f"【随叶云盘】您的注册验证码：{code}")
    msg['Subject'] = '随叶云盘 - 邮箱验证'
    send_email = '你的outlook邮箱@outlook.com'
    msg['From'] = send_email
    msg['To'] = to_email

    try:
        s = smtplib.SMTP('smtp.office365.com', 587)
        s.starttls()
        s.login(send_email, "你的outlook密码")
        s.sendmail(send_email, to_email, msg.as_string())
        s.quit()
    except:
        pass
    return code

def generate_graph_code():
    code = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    graph_codes[code] = time.time() + 300
    return code

@app.route('/')
def home():
    if 'user' not in session:
        return redirect('/login')
    fs = os.listdir(UPLOAD)
    user_info = users.get(session['user'], {})
    return render_template('index.html', files=fs, shares=shares, user=user_info)

@app.route('/login', methods=['GET','POST'])
def login():
    if 'user' in session:
        return redirect('/')
    if request.method == 'POST':
        u = request.form['user']
        p = request.form['pwd']
        gcode = request.form['graph_code']
        if gcode not in graph_codes or time.time() > graph_codes[gcode]:
            flash('图形验证码错误或已过期')
            return redirect('/login')
        if u in users and users[u]['pwd'] == p:
            session['user'] = u
            return redirect('/')
        flash('账号或密码错误')
        return redirect('/login')
    return render_template('login.html', graph_code=generate_graph_code())

@app.route('/register', methods=['GET','POST'])
def register():
    if 'user' in session:
        return redirect('/')
    if request.method == 'POST':
        reg_type = request.form['reg_type']
        u = request.form['user']
        p = request.form['pwd']
        gcode = request.form['graph_code']
        if gcode not in graph_codes or time.time() > graph_codes[gcode]:
            flash('图形验证码错误或已过期')
            return redirect('/register')
        if len(p)!=6 or not any(c.isalpha() for c in p) or not any(c.isdigit() for c in p):
            flash('密码必须6位，包含字母+数字')
            return redirect('/register')
        if u in users:
            flash('账号已存在')
            return redirect('/register')
        if reg_type == 'email':
            input_code = request.form['email_code']
            if codes.get(u) != input_code:
                flash('邮箱验证码错误')
                return redirect('/register')
            users[u] = {'pwd':p,'username':u.split('@')[0],'avatar':''}
        else:
            users[u] = {'pwd':p,'username':u,'avatar':''}
        save_users()
        session['user'] = u
        return redirect('/')
    return render_template('register.html', graph_code=generate_graph_code())

@app.route('/send_email_code', methods=['POST'])
def send_email_code():
    email = request.form['email']
    send_code(email)
    return jsonify({'status':'ok'})

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect('/login')
    if 'file' not in request.files:
        flash('请选择文件')
        return redirect('/')
    file = request.files['file']
    if not file.filename:
        flash('文件名为空')
        return redirect('/')
    filename = secure_filename(file.filename)
    dst = os.path.join(UPLOAD, filename)
    if dll:
        temp_path = os.path.join(os.getcwd(), 'tmp_'+filename)
        file.save(temp_path)
        if dll.isOver5GB(temp_path.encode()):
            os.remove(temp_path)
            flash('文件超过5GB')
            return redirect('/')
        dll.fastCopy(temp_path.encode(), dst.encode())
        os.remove(temp_path)
    else:
        file.save(dst)
        if os.path.getsize(dst) > 5368709120:
            os.remove(dst)
            flash('文件超过5GB')
            return redirect('/')
    flash('上传成功')
    return redirect('/')

@app.route('/download/<filename>')
def download(filename):
    if 'user' not in session:
        return redirect('/login')
    return send_from_directory(UPLOAD, filename, as_attachment=True)

@app.route('/delete/<filename>')
def delete(filename):
    if 'user' not in session:
        return redirect('/login')
    path = os.path.join(UPLOAD, filename)
    if os.path.exists(path):
        os.remove(path)
    for k in list(shares.keys()):
        if shares[k]['filename'] == filename:
            del shares[k]
    flash('已删除')
    return redirect('/')

@app.route('/create_share', methods=['POST'])
def create_share():
    if 'user' not in session:
        return redirect('/login')
    filename = request.form.get('filename')
    days = int(request.form.get('days',0))
    need_code = request.form.get('need_code','no')
    sid = str(uuid.uuid4())[:8]
    ecode = ''.join(random.choices(string.ascii_letters+string.digits,k=4)) if need_code=='yes' else ''
    exp = 0 if days==0 else time.time()+days*86400
    shares[sid] = {
        'filename':filename,
        'expire':exp,
        'extract_code':ecode,
        'creator':session['user']
    }
    flash('分享链接已生成')
    return redirect('/')

@app.route('/s/<sid>', methods=['GET','POST'])
def share_down(sid):
    if sid not in shares:
        return '分享不存在或已失效',404
    info = shares[sid]
    if info['expire']!=0 and time.time()>info['expire']:
        del shares[sid]
        return '分享已过期',403

    share_user = users.get(info['creator'], {'username':'随叶用户','avatar':''})

    if not info['extract_code']:
        return send_from_directory(UPLOAD, info['filename'], as_attachment=True)
    if request.method == 'GET':
        return render_template('extract.html', share_code=sid, share_user=share_user)
    if request.form.get('extract_code') == info['extract_code']:
        return send_from_directory(UPLOAD, info['filename'], as_attachment=True)
    return '提取码错误',403

@app.route('/profile', methods=['GET','POST'])
def profile():
    if 'user' not in session:
        return redirect('/login')
    uname = session['user']
    if request.method == 'POST':
        new_name = request.form.get('username','')
        avatar = request.files.get('avatar')
        if new_name:
            users[uname]['username'] = new_name
        if avatar and avatar.filename:
            ext = avatar.filename.split('.')[-1]
            avt_name = uuid.uuid4().hex+'.'+ext
            avt_path = os.path.join(AVATAR, avt_name)
            avatar.save(avt_path)
            users[uname]['avatar'] = avt_name
        save_users()
        flash('资料已保存')
        return redirect('/profile')
    return render_template('profile.html', user=users.get(uname,{}))

@app.route('/logout')
def logout():
    session.pop('user',None)
    return redirect('/login')

@app.route('/avatar/<name>')
def get_avt(name):
    path = os.path.join(AVATAR, name)
    if os.path.exists(path):
        return send_from_directory(AVATAR, name)
    return '',404

if __name__ == '__main__':
    app.run(debug=True, threaded=True)