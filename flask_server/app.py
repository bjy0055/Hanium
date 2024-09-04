from flask import Flask, request, render_template, redirect, url_for, session, flash, send_file
from flask_session import Session
import os
import zipfile
import pdfplumber
import mammoth
import re
from lxml import etree
from werkzeug.security import generate_password_hash, check_password_hash
import io
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
Session(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# 기본 아이디와 비밀번호 설정
USER_CREDENTIALS = {
    'admin': 'password'
}

# 개인정보 마스킹 함수 (정규식 사용)
def maskText(text):
    # 전화번호 마스킹 먼저 처리 (예: 010-1234-5678 -> [PHONE])
    maskedText = re.sub(
       r'(\d{2,3})-?(\d{3,4})-?(\d{4})',
        r'[PHONE]',
        text
    )

    # 이메일 마스킹 (example@example.com -> [EMAIL])
    maskedText = re.sub(
        r'(\w+)(@\w+\.\w+)',
        r'[EMAIL]',
        maskedText
    )

    # 주민등록번호 마스킹 (990101-1234567 -> [SSN])
    maskedText = re.sub(
         r'(\d{6})-([1-4])(\d{6})',
        r'[SSN]',
        maskedText
    )

    # 주소 마스킹 (서울특별시 강남구 -> [ADDRESS])
    maskedText = re.sub(
        r'([가-힣]+[시|도])\s+([가-힣]+[구|군|읍|면|동])',
        r'[ADDRESS]',
        maskedText
    )

    # 이름 마스킹 (홍길동 -> 홍*동)
    maskedText = re.sub(
        r'([가-힣]{2})([가-힣]{1})',
        r'\1*\2',
        maskedText
    )

    return maskedText


# 파일에서 텍스트 추출 함수
def extractTextFromFile(file_path, file_type):
    text = ""
    if file_type == "txt":
        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read()
    elif file_type == "docx":
        with open(file_path, "rb") as file:
            result = mammoth.extract_raw_text(file)
            text = result.value
    elif file_type == "pdf":
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text()
    elif file_type == "pptx":
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if file.startswith('ppt/slides/slide') and file.endswith('.xml'):
                    with zip_ref.open(file) as xml_file:
                        content = xml_file.read()
                        parsed_xml = etree.fromstring(content)
                        text += extractTextFromSlide(parsed_xml)
    return text

def extractTextFromSlide(parsed_xml):
    text = ""
    paragraphs = parsed_xml.findall('.//a:t', namespaces={'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
    for paragraph in paragraphs:
        text += paragraph.text
    return text

@app.route('/')
def cover():
    return render_template('cover.html')

# Database setup
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # 1. 입력 데이터 유효성 검사
        if not username or not email or not password or not confirm_password:
            flash('모든 필드를 입력해야 합니다.')
            return redirect(url_for('signup'))

        # 2. 비밀번호 확인 일치 여부 검사
        if password != confirm_password:
            flash('비밀번호가 일치하지 않습니다.')
            return redirect(url_for('signup'))

        # 3. 비밀번호 해시 처리
        hashed_password = generate_password_hash(password)

        # 4. 중복 사용자 체크 및 데이터베이스 저장
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user:
            flash('이미 존재하는 사용자입니다.')
            return redirect(url_for('signup'))
        
        conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                     (username, email, hashed_password))
        conn.commit()
        conn.close()

        flash('회원가입이 완료되었습니다! 로그인하세요.')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials. Please try again.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('cover'))

@app.route('/home')
def home():
    if 'username' in session:
        return render_template('home.html')
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'username' in session:  # 로그인 여부 확인
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file selected')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('No file selected')
                return redirect(request.url)
            if file:
                # 원본 파일 저장
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(file_path)

                # 파일 유형 결정
                file_type = file.filename.split('.')[-1].lower()

                # 파일에서 텍스트 추출 및 가명 처리
                text = extractTextFromFile(file_path, file_type)
                masked_text = maskText(text)

                # 가명처리된 텍스트를 새 파일로 저장
                output_file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'masked_' + file.filename)
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(masked_text)

                # 원본 파일 삭제
                os.remove(file_path)

                # 가명처리된 파일 다운로드 링크 제공
                return render_template('upload.html', input_text=text, masked_text=masked_text, download_link=output_file_path)
        return render_template('upload.html', input_text='', masked_text='')
    return redirect(url_for('login'))

@app.route('/download/<filename>')
def download_file(filename):
    if 'username' in session:  # 로그인 여부 확인
        file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        return send_file(file_path, as_attachment=True)
    return redirect(url_for('login'))

@app.route('/my_page')
def my_page():
    if 'username' in session:
        return render_template('my_page.html')
    return redirect(url_for('login'))

@app.route('/document_management')
def document_management():
    if 'username' in session:
        return render_template('document_management.html')
    return redirect(url_for('login'))

@app.route('/customer_support')
def customer_support():
    if 'username' in session:
        return render_template('customer_support.html')
    return redirect(url_for('login'))

@app.route('/text', methods=['GET', 'POST'])
def text():
    if 'username' in session:
        original_text = ""
        masked_text = ""
        
        if request.method == 'POST':
            original_text = request.form.get('input_text', '')
            masked_text = maskText(original_text)  # maskText는 가명처리 함수
        
        return render_template('text.html', original_text=original_text, masked_text=masked_text)
    return redirect(url_for('login'))




if __name__ == "__main__":
    app.run(debug=True, port=5001)
