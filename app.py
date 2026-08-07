import os
import io
import csv
import json
import base64
import secrets
from datetime import datetime, timedelta
import pyotp
import qrcode
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, send_file, jsonify, session, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                          login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)
# SECRET_KEY は環境変数 LMS_SECRET_KEY から読み込む。未設定時は起動ごとにランダム生成
# （＝再起動で全セッション無効化）し、本番では必ず環境変数を設定するよう警告する。
_secret = os.environ.get('LMS_SECRET_KEY')
if not _secret:
    _secret = secrets.token_hex(32)
    print('[警告] LMS_SECRET_KEY が未設定です。本番環境では固定の秘密鍵を環境変数に設定してください。')
app.config['SECRET_KEY'] = _secret

# セッションCookieのセキュリティ強化
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# HTTPS 配信時は環境変数 LMS_HTTPS=1 を設定して Secure 属性を有効化する
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('LMS_HTTPS') == '1'

@app.template_filter('fromjson')
def fromjson_filter(s):
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}
# DB接続先は環境変数 LMS_DATABASE_URI で上書き可（テスト隔離・PostgreSQL移行に対応）。既定はSQLite。
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('LMS_DATABASE_URI', 'sqlite:///lms.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'ログインが必要です'

from functools import wraps

def skillgrowth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'skillgrowth':
            abort(403)
        return f(*args, **kwargs)
    return decorated

def company_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('skillgrowth', 'company_admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ===== モデル定義 =====

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    users = db.relationship('User', backref='company', lazy=True)
    curricula = db.relationship('CompanyCurriculum', backref='company', lazy=True, cascade='all, delete-orphan')


class CompanyCurriculum(db.Model):
    """会社ごとに受講可能なカリキュラムを制限する"""
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    curriculum_name = db.Column(db.String(200), nullable=False)
    __table_args__ = (db.UniqueConstraint('company_id', 'curriculum_name'),)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='employee')  # skillgrowth / company_admin / employee
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    full_name = db.Column(db.String(100))
    employee_id = db.Column(db.String(50))
    department = db.Column(db.String(100))
    employment_type = db.Column(db.String(50))
    hire_date = db.Column(db.Date)
    force_password_change = db.Column(db.Boolean, default=False)
    # ログイン試行回数制限（総当たり対策）
    failed_login_count = db.Column(db.Integer, default=0)
    lockout_until = db.Column(db.DateTime)
    # MFA（TOTP多要素認証・任意）
    mfa_secret = db.Column(db.String(32))
    mfa_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    enrollments = db.relationship('Enrollment', backref='user', lazy=True)

    @property
    def is_skillgrowth(self):
        return self.role == 'skillgrowth'

    @property
    def is_company_admin(self):
        return self.role == 'company_admin'

    @property
    def is_admin(self):
        return self.role in ('skillgrowth', 'company_admin')


class ActiveSession(db.Model):
    """二重ログイン防止 - 同一ユーザーの最新セッションのみ有効"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    token = db.Column(db.String(100), nullable=False)
    logged_in_at = db.Column(db.DateTime, default=datetime.utcnow)


class LoginSession(db.Model):
    """ログイン/ログアウトの証跡（助成金審査の実施期間証明）。1ログイン=1レコードを追記保存。"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_at = db.Column(db.DateTime, default=datetime.utcnow)
    logout_at = db.Column(db.DateTime)  # 明示ログアウト or 二重ログインによる強制終了時に記録
    logout_reason = db.Column(db.String(30))  # 'logout' / 'forced'（別端末ログイン）
    ip_address = db.Column(db.String(50))


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    training_type = db.Column(db.String(100))
    category = db.Column(db.String(100))
    total_hours = db.Column(db.Float, default=0)
    pass_score = db.Column(db.Integer, default=80)
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    lessons = db.relationship('Lesson', backref='course', lazy=True, order_by='Lesson.order')
    enrollments = db.relationship('Enrollment', backref='course', lazy=True)
    quizzes = db.relationship('Quiz', backref='course', lazy=True)


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    video_url = db.Column(db.String(500))
    duration_minutes = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Integer, default=0)
    order = db.Column(db.Integer, default=0)
    progress_records = db.relationship('LessonProgress', backref='lesson', lazy=True, cascade='all, delete-orphan')


class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    questions = db.relationship('Question', backref='quiz', lazy=True, order_by='Question.order')


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(300))
    option_b = db.Column(db.String(300))
    option_c = db.Column(db.String(300))
    option_d = db.Column(db.String(300))
    correct_answer = db.Column(db.String(1))
    order = db.Column(db.Integer, default=0)


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    total_study_seconds = db.Column(db.Integer, default=0)  # 実際の視聴秒数（心拍ベース）
    quiz_score = db.Column(db.Integer)
    quiz_attempts = db.Column(db.Integer, default=0)
    progress_percent = db.Column(db.Integer, default=0)  # レッスン完了ベースの進捗率（%）
    status = db.Column(db.String(20), default='enrolled')
    lesson_progress = db.relationship('LessonProgress', backref='enrollment', lazy=True)

    @property
    def total_study_minutes(self):
        return (self.total_study_seconds or 0) // 60


class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollment.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    actual_watch_seconds = db.Column(db.Integer, default=0)  # 実測視聴秒数（改ざん防止：APIのみ更新）
    last_position_seconds = db.Column(db.Integer, default=0)  # レジュメ用
    last_heartbeat_at = db.Column(db.DateTime)  # 改ざん防止：サーバ実時間ベースで加算量を制限
    is_completed = db.Column(db.Boolean, default=False)


class StudyLog(db.Model):
    """受講ログ - 労働局提出用。値はAPIが自動生成し管理者が編集不可"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=True)
    login_at = db.Column(db.DateTime, default=datetime.utcnow)
    logout_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer, default=0)  # 秒単位
    ip_address = db.Column(db.String(50))


class QuizAttempt(db.Model):
    """テスト解答履歴 - 全履歴を保存"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Integer)
    answers_json = db.Column(db.Text)  # JSON: {"question_id": "A", ...}
    ip_address = db.Column(db.String(50))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ===== 認証前処理 =====

@app.before_request
def check_session_and_password():
    exempt = {'login', 'logout', 'static', 'change_password'}
    if not current_user.is_authenticated:
        return
    if request.endpoint in exempt:
        return

    # 初回パスワード変更強制
    if current_user.force_password_change:
        return redirect(url_for('change_password'))

    # 二重ログイン防止: セッショントークンが最新でなければ強制ログアウト。
    # トークンが欠損している場合もチェックをすり抜けさせず再ログインを求める。
    token = session.get('session_token')
    active = ActiveSession.query.filter_by(user_id=current_user.id).first()
    if not token or not active or active.token != token:
        close_login_session('forced')
        logout_user()
        flash('別の端末でログインされたため、セッションが終了しました。', 'warning')
        return redirect(url_for('login'))


# ===== 認証 =====

def close_login_session(reason):
    """現在のログイン証跡にログアウト時刻を記録する（未記録時のみ）。"""
    log_id = session.get('login_session_id')
    if not log_id:
        return
    log = LoginSession.query.get(log_id)
    if log and log.logout_at is None:
        log.logout_at = datetime.utcnow()
        log.logout_reason = reason
        db.session.commit()
    session.pop('login_session_id', None)


MAX_LOGIN_ATTEMPTS = 5   # 連続失敗の上限
LOCKOUT_MINUTES = 15     # 上限到達時のロック時間（分）


def _establish_session(user):
    """パスワード（＋MFA）検証後に実セッションを確立し、証跡を記録する。"""
    token = secrets.token_hex(32)
    active = ActiveSession.query.filter_by(user_id=user.id).first()
    if active:
        active.token = token
        active.logged_in_at = datetime.utcnow()
    else:
        db.session.add(ActiveSession(user_id=user.id, token=token))
    login_log = LoginSession(user_id=user.id, ip_address=request.remote_addr)
    db.session.add(login_log)
    # ログイン成功で失敗カウンタをリセット
    user.failed_login_count = 0
    user.lockout_until = None
    db.session.commit()
    login_user(user)
    session['session_token'] = token
    session['login_session_id'] = login_log.id


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()

        # アカウントロック中の判定（総当たり対策）
        if user and user.lockout_until and user.lockout_until > datetime.utcnow():
            remain = int((user.lockout_until - datetime.utcnow()).total_seconds() // 60) + 1
            flash(f'ログイン試行回数の上限を超えました。約{remain}分後に再度お試しください。', 'danger')
            return render_template('login.html')

        if user and check_password_hash(user.password_hash, request.form['password']):
            # MFA有効ユーザーは2要素目の検証へ（本認証は保留）
            if user.mfa_enabled and user.mfa_secret:
                session['mfa_pending_user_id'] = user.id
                return redirect(url_for('mfa_verify'))
            _establish_session(user)
            return redirect(url_for('dashboard'))

        # 認証失敗: 失敗カウントを加算し、上限でロック
        if user:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= MAX_LOGIN_ATTEMPTS:
                user.lockout_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_count = 0
                db.session.commit()
                flash(f'ログイン試行回数の上限を超えました。約{LOCKOUT_MINUTES}分間ロックされます。', 'danger')
                return render_template('login.html')
            db.session.commit()
        flash('ユーザー名またはパスワードが正しくありません', 'danger')
    return render_template('login.html')


@app.route('/mfa/verify', methods=['GET', 'POST'])
def mfa_verify():
    """ログイン第2要素（TOTP）の検証。パスワード認証済みユーザーのみ。"""
    uid = session.get('mfa_pending_user_id')
    if not uid:
        return redirect(url_for('login'))
    user = User.query.get(uid)
    if not user or not user.mfa_enabled or not user.mfa_secret:
        session.pop('mfa_pending_user_id', None)
        return redirect(url_for('login'))
    if request.method == 'POST':
        code = request.form.get('code', '').strip().replace(' ', '')
        if pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1):
            session.pop('mfa_pending_user_id', None)
            _establish_session(user)
            return redirect(url_for('dashboard'))
        flash('認証コードが正しくありません。', 'danger')
    return render_template('mfa_verify.html')


@app.route('/mfa/setup', methods=['GET', 'POST'])
@login_required
def mfa_setup():
    """MFA（TOTP）の有効化。QRを表示し、コード検証に成功したら有効化する。"""
    if request.method == 'POST':
        secret = session.get('mfa_setup_secret')
        code = request.form.get('code', '').strip().replace(' ', '')
        if secret and pyotp.TOTP(secret).verify(code, valid_window=1):
            current_user.mfa_secret = secret
            current_user.mfa_enabled = True
            db.session.commit()
            session.pop('mfa_setup_secret', None)
            flash('多要素認証を有効化しました。', 'success')
            return redirect(url_for('mfa_setup'))
        flash('認証コードが正しくありません。QRを読み込み直して再度お試しください。', 'danger')

    if current_user.mfa_enabled:
        return render_template('mfa_setup.html', enabled=True, qr_data_uri=None, secret=None)

    # 未有効: 新しいシークレットとプロビジョニングQRを生成
    secret = pyotp.random_base32()
    session['mfa_setup_secret'] = secret
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=current_user.username, issuer_name='Skillgrowth LMS')
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_data_uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    return render_template('mfa_setup.html', enabled=False,
                           qr_data_uri=qr_data_uri, secret=secret)


@app.route('/mfa/disable', methods=['POST'])
@login_required
def mfa_disable():
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    db.session.commit()
    flash('多要素認証を無効化しました。', 'success')
    return redirect(url_for('mfa_setup'))


@app.route('/logout')
@login_required
def logout():
    close_login_session('logout')
    ActiveSession.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    logout_user()
    return redirect(url_for('login'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if len(new_pw) < 8:
            flash('パスワードは8文字以上で設定してください', 'danger')
        elif new_pw != confirm:
            flash('パスワードが一致しません', 'danger')
        else:
            current_user.password_hash = generate_password_hash(new_pw)
            current_user.force_password_change = False
            db.session.commit()
            flash('パスワードを変更しました', 'success')
            return redirect(url_for('dashboard'))
    return render_template('change_password.html')


# ===== ダッシュボード =====

@app.route('/')
@login_required
def dashboard():
    if current_user.role == 'skillgrowth':
        total_users = User.query.filter_by(role='employee').count()
        total_courses = Course.query.count()
        total_enrollments = Enrollment.query.count()
        completed = Enrollment.query.filter_by(status='completed').count()
        recent_logs = (db.session.query(StudyLog, User, Course)
                       .join(User, StudyLog.user_id == User.id)
                       .join(Course, StudyLog.course_id == Course.id)
                       .order_by(StudyLog.login_at.desc()).limit(10).all())
        return render_template('admin_dashboard.html',
                               total_users=total_users, total_courses=total_courses,
                               total_enrollments=total_enrollments, completed=completed,
                               recent_logs=recent_logs)
    elif current_user.role == 'company_admin':
        company = current_user.company
        employees = User.query.filter_by(company_id=current_user.company_id, role='employee').all()
        employee_ids = [e.id for e in employees]
        enrollments = (Enrollment.query.filter(Enrollment.user_id.in_(employee_ids)).all()
                       if employee_ids else [])
        completed = sum(1 for e in enrollments if e.status == 'completed')
        in_progress = sum(1 for e in enrollments if e.status == 'in_progress')
        return render_template('ca_dashboard.html',
                               company=company, employees=employees,
                               total_enrollments=len(enrollments),
                               completed=completed, in_progress=in_progress)
    else:
        enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
        enrolled_ids = [e.course_id for e in enrollments]
        base_q = Course.query.filter_by(is_published=True).filter(~Course.id.in_(enrolled_ids))
        if current_user.company_id:
            allowed_curricula = [cc.curriculum_name for cc in
                                 CompanyCurriculum.query.filter_by(company_id=current_user.company_id).all()]
            if allowed_curricula:
                base_q = base_q.filter(Course.category.in_(allowed_curricula))
        available_courses = base_q.all()
        return render_template('employee_dashboard.html',
                               enrollments=enrollments, available_courses=available_courses)


# ===== コース管理（管理者） =====

@app.route('/admin/courses')
@login_required
def admin_courses():
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    courses = Course.query.order_by(Course.created_at.desc()).all()
    return render_template('admin_courses.html', courses=courses)


@app.route('/admin/courses/new', methods=['GET', 'POST'])
@login_required
def new_course():
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        course = Course(
            title=request.form['title'],
            description=request.form.get('description', ''),
            category=request.form.get('category', ''),
            training_type=request.form.get('training_type', ''),
            total_hours=float(request.form.get('total_hours') or 0),
            pass_score=int(request.form.get('pass_score') or 80),
            created_by=current_user.id
        )
        db.session.add(course)
        db.session.commit()
        flash('コースを作成しました', 'success')
        return redirect(url_for('edit_course', course_id=course.id))
    return render_template('course_form.html', course=None)


@app.route('/admin/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        course.title = request.form['title']
        course.description = request.form.get('description', '')
        course.category = request.form.get('category', '')
        course.training_type = request.form.get('training_type', '')
        course.total_hours = float(request.form.get('total_hours') or 0)
        course.pass_score = int(request.form.get('pass_score') or 80)
        course.is_published = 'is_published' in request.form
        db.session.commit()
        flash('コースを更新しました', 'success')
    return render_template('course_form.html', course=course)


@app.route('/admin/courses/<int:course_id>/lessons/add', methods=['POST'])
@login_required
def add_lesson(course_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    lesson = Lesson(
        course_id=course_id,
        title=request.form['title'],
        content=request.form['content'],
        video_url=request.form.get('video_url', ''),
        duration_minutes=int(request.form.get('duration_minutes', 0)),
        order=len(course.lessons) + 1
    )
    db.session.add(lesson)
    db.session.commit()
    flash('レッスンを追加しました', 'success')
    return redirect(url_for('edit_course', course_id=course_id))


@app.route('/admin/lessons/<int:lesson_id>/delete', methods=['POST'])
@login_required
def delete_lesson(lesson_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    lesson = Lesson.query.get_or_404(lesson_id)
    course_id = lesson.course_id
    StudyLog.query.filter_by(lesson_id=lesson_id).update({'lesson_id': None})
    db.session.delete(lesson)  # cascade: LessonProgress も削除
    db.session.commit()
    flash('レッスンを削除しました', 'success')
    return redirect(url_for('edit_course', course_id=course_id))


@app.route('/admin/courses/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    title = course.title
    for enrollment in list(course.enrollments):
        LessonProgress.query.filter_by(enrollment_id=enrollment.id).delete()
        db.session.delete(enrollment)
    StudyLog.query.filter_by(course_id=course_id).update({'lesson_id': None})
    StudyLog.query.filter_by(course_id=course_id).delete()
    QuizAttempt.query.filter_by(course_id=course_id).delete()
    for quiz in list(course.quizzes):
        Question.query.filter_by(quiz_id=quiz.id).delete()
        db.session.delete(quiz)
    for lesson in list(course.lessons):
        db.session.delete(lesson)
    db.session.delete(course)
    db.session.commit()
    flash(f'コース「{title}」を削除しました', 'success')
    return redirect(url_for('admin_courses'))


# ===== クイズ管理 =====

@app.route('/admin/courses/<int:course_id>/quiz', methods=['GET', 'POST'])
@login_required
def manage_quiz(course_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    quiz = Quiz.query.filter_by(course_id=course_id).first()
    if request.method == 'POST':
        if not quiz:
            quiz = Quiz(course_id=course_id, title=f'{course.title} 理解度テスト')
            db.session.add(quiz)
            db.session.commit()
        question = Question(
            quiz_id=quiz.id,
            question_text=request.form['question_text'],
            option_a=request.form['option_a'],
            option_b=request.form['option_b'],
            option_c=request.form.get('option_c', ''),
            option_d=request.form.get('option_d', ''),
            correct_answer=request.form['correct_answer'],
            order=len(quiz.questions) + 1
        )
        db.session.add(question)
        db.session.commit()
        flash('問題を追加しました', 'success')
    return render_template('manage_quiz.html', course=course, quiz=quiz)


@app.route('/admin/questions/<int:question_id>/delete', methods=['POST'])
@login_required
def delete_question(question_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    question = Question.query.get_or_404(question_id)
    course_id = question.quiz.course_id
    db.session.delete(question)
    db.session.commit()
    flash('問題を削除しました', 'success')
    return redirect(url_for('manage_quiz', course_id=course_id))


# ===== 受講者管理（管理者） =====

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    users = (User.query.filter(User.role.in_(['employee', 'company_admin']))
             .order_by(User.full_name).all())
    companies = Company.query.order_by(Company.name).all()
    return render_template('admin_users.html', users=users, companies=companies)


@app.route('/admin/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    companies = Company.query.order_by(Company.name).all()
    if request.method == 'POST':
        hire_date = None
        if request.form.get('hire_date'):
            hire_date = datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date()
        role = request.form.get('role', 'employee')
        if role not in ('employee', 'company_admin'):
            role = 'employee'
        company_id = request.form.get('company_id') or None
        if company_id:
            company_id = int(company_id)
        user = User(
            username=request.form['username'],
            email=request.form['email'],
            password_hash=generate_password_hash(request.form['password']),
            full_name=request.form['full_name'],
            employee_id=request.form.get('employee_id', ''),
            department=request.form.get('department', ''),
            employment_type=request.form.get('employment_type', ''),
            hire_date=hire_date,
            role=role,
            company_id=company_id,
            force_password_change='force_pw' in request.form
        )
        db.session.add(user)
        db.session.commit()
        flash('ユーザーを登録しました', 'success')
        return redirect(url_for('admin_users'))
    return render_template('user_form.html', user=None, companies=companies)


@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    companies = Company.query.order_by(Company.name).all()
    if request.method == 'POST':
        user.full_name = request.form['full_name']
        user.email = request.form['email']
        user.employee_id = request.form.get('employee_id', '')
        user.department = request.form.get('department', '')
        user.employment_type = request.form.get('employment_type', '')
        if request.form.get('hire_date'):
            user.hire_date = datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date()
        company_id = request.form.get('company_id') or None
        if company_id:
            company_id = int(company_id)
        user.company_id = company_id
        role = request.form.get('role', user.role)
        if role in ('employee', 'company_admin'):
            user.role = role
        if request.form.get('password'):
            user.password_hash = generate_password_hash(request.form['password'])
            user.force_password_change = 'force_pw' in request.form
        db.session.commit()
        flash('ユーザー情報を更新しました', 'success')
        return redirect(url_for('admin_users'))
    return render_template('user_form.html', user=user, companies=companies)


# ===== 受講管理 =====

@app.route('/admin/enrollments')
@login_required
def admin_enrollments():
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    enrollments = (db.session.query(Enrollment, User, Course)
                   .join(User, Enrollment.user_id == User.id)
                   .join(Course, Enrollment.course_id == Course.id)
                   .order_by(Enrollment.enrolled_at.desc()).all())
    users = User.query.filter_by(role='employee').all()
    courses = Course.query.filter_by(is_published=True).all()
    return render_template('admin_enrollments.html',
                           enrollments=enrollments, users=users, courses=courses)


@app.route('/admin/enrollments/add', methods=['POST'])
@login_required
def add_enrollment():
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    user_id = int(request.form['user_id'])
    course_id = int(request.form['course_id'])
    if Enrollment.query.filter_by(user_id=user_id, course_id=course_id).first():
        flash('すでに受講登録済みです', 'warning')
    else:
        db.session.add(Enrollment(user_id=user_id, course_id=course_id))
        db.session.commit()
        flash('受講登録しました', 'success')
    return redirect(url_for('admin_enrollments'))


# ===== 会社管理（Skillgrowth専用） =====

@app.route('/admin/companies')
@login_required
def admin_companies():
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    companies = Company.query.order_by(Company.name).all()
    return render_template('admin_companies.html', companies=companies)


@app.route('/admin/companies/new', methods=['GET', 'POST'])
@login_required
def new_company():
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        company = Company(name=request.form['name'])
        db.session.add(company)
        db.session.commit()
        flash('会社を登録しました', 'success')
        return redirect(url_for('admin_companies'))
    return render_template('company_form.html', company=None)


@app.route('/admin/companies/<int:company_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_company(company_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    company = Company.query.get_or_404(company_id)
    if request.method == 'POST':
        company.name = request.form['name']
        db.session.commit()
        flash('会社情報を更新しました', 'success')
        return redirect(url_for('admin_companies'))
    return render_template('company_form.html', company=company)


@app.route('/admin/companies/<int:company_id>/delete', methods=['POST'])
@login_required
def delete_company(company_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    company = Company.query.get_or_404(company_id)
    User.query.filter_by(company_id=company_id).update({'company_id': None})
    db.session.delete(company)
    db.session.commit()
    flash('会社を削除しました', 'success')
    return redirect(url_for('admin_companies'))


@app.route('/admin/companies/<int:company_id>/curricula', methods=['GET', 'POST'])
@login_required
def admin_company_curricula(company_id):
    """会社ごとに受講許可するカリキュラムを設定"""
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    company = Company.query.get_or_404(company_id)
    all_curricula = sorted({c.category for c in Course.query.filter(
        Course.category != None, Course.category != '').all()})
    if request.method == 'POST':
        selected = set(request.form.getlist('curricula'))
        CompanyCurriculum.query.filter_by(company_id=company_id).delete()
        for name in selected:
            db.session.add(CompanyCurriculum(company_id=company_id, curriculum_name=name))
        db.session.commit()
        flash('受講カリキュラムを更新しました', 'success')
        return redirect(url_for('admin_companies'))
    allowed = {cc.curriculum_name for cc in company.curricula}
    return render_template('admin_company_curricula.html',
                           company=company, all_curricula=all_curricula, allowed=allowed)


# ===== 会社管理者向けルート =====

@app.route('/ca/users')
@login_required
def ca_users():
    if current_user.role not in ('skillgrowth', 'company_admin'):
        return redirect(url_for('dashboard'))
    if current_user.role == 'company_admin':
        users = (User.query.filter_by(company_id=current_user.company_id, role='employee')
                 .order_by(User.full_name).all())
    else:
        users = User.query.filter_by(role='employee').order_by(User.full_name).all()
    return render_template('ca_users.html', users=users)


@app.route('/ca/users/new', methods=['GET', 'POST'])
@login_required
def ca_new_user():
    if current_user.role not in ('skillgrowth', 'company_admin'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        hire_date = None
        if request.form.get('hire_date'):
            hire_date = datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date()
        user = User(
            username=request.form['username'],
            email=request.form['email'],
            password_hash=generate_password_hash(request.form['password']),
            full_name=request.form['full_name'],
            employee_id=request.form.get('employee_id', ''),
            department=request.form.get('department', ''),
            employment_type=request.form.get('employment_type', ''),
            hire_date=hire_date,
            role='employee',
            company_id=current_user.company_id,
            force_password_change='force_pw' in request.form
        )
        db.session.add(user)
        db.session.commit()
        flash('受講者を登録しました', 'success')
        return redirect(url_for('ca_users'))
    return render_template('ca_user_form.html', user=None)


@app.route('/ca/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def ca_edit_user(user_id):
    if current_user.role not in ('skillgrowth', 'company_admin'):
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    if current_user.role == 'company_admin' and user.company_id != current_user.company_id:
        abort(403)
    if request.method == 'POST':
        user.full_name = request.form['full_name']
        user.email = request.form['email']
        user.employee_id = request.form.get('employee_id', '')
        user.department = request.form.get('department', '')
        user.employment_type = request.form.get('employment_type', '')
        if request.form.get('hire_date'):
            user.hire_date = datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date()
        if request.form.get('password'):
            user.password_hash = generate_password_hash(request.form['password'])
            user.force_password_change = 'force_pw' in request.form
        db.session.commit()
        flash('受講者情報を更新しました', 'success')
        return redirect(url_for('ca_users'))
    return render_template('ca_user_form.html', user=user)


@app.route('/ca/reports')
@login_required
def ca_reports():
    if current_user.role not in ('skillgrowth', 'company_admin'):
        return redirect(url_for('dashboard'))
    if current_user.role == 'company_admin':
        employees = (User.query.filter_by(company_id=current_user.company_id, role='employee').all())
    else:
        employees = User.query.filter_by(role='employee').all()
    employee_ids = [e.id for e in employees]
    enrollments = (db.session.query(Enrollment, User, Course)
                   .join(User, Enrollment.user_id == User.id)
                   .join(Course, Enrollment.course_id == Course.id)
                   .filter(Enrollment.user_id.in_(employee_ids))
                   .order_by(User.full_name).all()) if employee_ids else []
    return render_template('ca_reports.html', enrollments=enrollments, employees=employees)


# ===== 受講（従業員） =====

@app.route('/courses/<int:course_id>/enroll', methods=['POST'])
@login_required
def enroll_course(course_id):
    if not Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first():
        db.session.add(Enrollment(user_id=current_user.id, course_id=course_id))
        db.session.commit()
    return redirect(url_for('study_course', course_id=course_id))


def compute_unlocked_lesson_ids(course, completed_lesson_ids):
    """未視聴制御: 各レッスンは、順序上の直前レッスンが完了している場合のみ解放する。
    先頭レッスンは常に解放。助成金要件「前チャプター完了まで次へ進めない」の担保。"""
    unlocked = set()
    prev_completed = True  # 先頭レッスンは常に解放
    for lesson in course.lessons:  # course.lessons は Lesson.order 昇順
        if prev_completed:
            unlocked.add(lesson.id)
        prev_completed = lesson.id in completed_lesson_ids
    return unlocked


@app.route('/courses/<int:course_id>/study')
@login_required
def study_course(course_id):
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first_or_404()

    if not enrollment.started_at:
        enrollment.started_at = datetime.utcnow()
        enrollment.status = 'in_progress'
        db.session.commit()

    completed_lesson_ids = {lp.lesson_id for lp in enrollment.lesson_progress if lp.is_completed}
    unlocked_lesson_ids = compute_unlocked_lesson_ids(course, completed_lesson_ids)

    lesson_id = request.args.get('lesson_id', type=int)
    current_lesson = None
    if lesson_id:
        current_lesson = next((l for l in course.lessons if l.id == lesson_id), None)
    # 未解放レッスンへの直接アクセスを拒否し、受講可能な先頭レッスンへ誘導
    if current_lesson is not None and current_lesson.id not in unlocked_lesson_ids:
        flash('前のチャプターを完了してから次に進んでください。', 'warning')
        current_lesson = None
    if current_lesson is None and course.lessons:
        # 未完了かつ解放済みの最初のレッスン（無ければ先頭）を選択
        current_lesson = next(
            (l for l in course.lessons
             if l.id in unlocked_lesson_ids and l.id not in completed_lesson_ids),
            course.lessons[0])

    # レジュメ位置を取得
    resume_seconds = 0
    if current_lesson:
        progress = LessonProgress.query.filter_by(
            enrollment_id=enrollment.id, lesson_id=current_lesson.id).first()
        if progress:
            resume_seconds = progress.last_position_seconds or 0

    quiz = Quiz.query.filter_by(course_id=course_id).first()
    all_completed = (len(completed_lesson_ids) == len(course.lessons)) if course.lessons else False

    # カリキュラム修了チェック（同カテゴリの全コース・全レッスン完了）
    curriculum_completed = False
    if course.category and all_completed:
        curr_courses = Course.query.filter_by(category=course.category).all()
        curriculum_completed = True
        for cc in curr_courses:
            enr = Enrollment.query.filter_by(user_id=current_user.id, course_id=cc.id).first()
            if not enr:
                curriculum_completed = False
                break
            done = {lp.lesson_id for lp in enr.lesson_progress if lp.is_completed}
            if any(l.id not in done for l in cc.lessons):
                curriculum_completed = False
                break

    return render_template('study.html',
                           course=course, enrollment=enrollment,
                           current_lesson=current_lesson,
                           completed_lesson_ids=completed_lesson_ids,
                           unlocked_lesson_ids=unlocked_lesson_ids,
                           resume_seconds=resume_seconds,
                           quiz=quiz,
                           all_lessons_completed=all_completed,
                           curriculum_completed=curriculum_completed)


@app.route('/courses/<int:course_id>/lessons/<int:lesson_id>/video_token')
@login_required
def video_token(course_id, lesson_id):
    """受講登録済みユーザーにのみ動画IDを返す。ページソースには埋め込まない。"""
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first_or_404()
    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course_id).first_or_404()
    url = lesson.video_url or ''
    if 'youtube.com/watch' in url:
        vid = url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        vid = url.split('youtu.be/')[1].split('?')[0]
    else:
        vid = ''
    return jsonify({'video_id': vid})


@app.route('/courses/<int:course_id>/lessons/<int:lesson_id>/set_duration', methods=['POST'])
@login_required
def set_lesson_duration(course_id, lesson_id):
    """YouTubeプレイヤーから取得した実際の動画時間をDBに保存する"""
    data = request.get_json(silent=True) or {}
    seconds = int(data.get('duration_seconds', 0))
    if seconds > 0:
        lesson = Lesson.query.filter_by(id=lesson_id, course_id=course_id).first_or_404()
        # 改ざん防止: 動画長は視聴時間の上限判定に使うため、未設定時のみ書き込む（write-once）。
        # 既に確定済みの値を受講者が後から書き換えられないようにする。
        if not lesson.duration_seconds:
            lesson.duration_seconds = seconds
            lesson.duration_minutes = max(1, seconds // 60)
            db.session.commit()
    return jsonify({'ok': True})


@app.route('/courses/<int:course_id>/lessons/<int:lesson_id>/certificate')
@login_required
def lesson_certificate(course_id, lesson_id):
    """各レッスン視聴完了後の修了証PDFを発行する"""
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first_or_404()
    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course_id).first_or_404()
    progress = LessonProgress.query.filter_by(
        enrollment_id=enrollment.id, lesson_id=lesson_id).first()
    if not progress or not progress.is_completed:
        return jsonify({'error': '未完了'}), 403
    course = Course.query.get(course_id)
    pdf = generate_lesson_certificate_pdf(current_user, course, lesson, progress)
    filename = f'修了証_{current_user.full_name or current_user.username}_{lesson.title}.pdf'
    return send_file(pdf, download_name=filename, as_attachment=True, mimetype='application/pdf')


@app.route('/courses/<int:course_id>/lessons/<int:lesson_id>/heartbeat', methods=['POST'])
@login_required
def lesson_heartbeat(course_id, lesson_id):
    """5秒ごとの視聴ハートビート。実際の視聴時間とレジュメ位置を記録"""
    data = request.get_json(silent=True) or {}
    position_seconds = int(data.get('position_seconds', 0))

    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first()
    if not enrollment:
        return jsonify({'ok': False}), 404

    # 未視聴制御: 未解放レッスンでは時間計測しない（API直叩き対策）
    course = Course.query.get_or_404(course_id)
    completed_ids = {lp.lesson_id for lp in enrollment.lesson_progress if lp.is_completed}
    if lesson_id not in compute_unlocked_lesson_ids(course, completed_ids):
        return jsonify({'ok': False, 'error': '前のチャプターが未完了です'}), 403

    progress = LessonProgress.query.filter_by(
        enrollment_id=enrollment.id, lesson_id=lesson_id).first()
    if not progress:
        progress = LessonProgress(
            enrollment_id=enrollment.id,
            lesson_id=lesson_id,
            started_at=datetime.utcnow()
        )
        db.session.add(progress)

    progress.last_position_seconds = position_seconds
    # 未完了レッスンのみ視聴時間を加算（完了済みの再視聴では加算しない）
    now = datetime.utcnow()
    if not progress.is_completed:
        # 改ざん防止: クライアント申告ではなく「サーバ側の前回ハートビートからの実経過時間」で加算。
        # 連打しても実時間ぶんしか増えず、一時停止・タブ切替の中断ぶんも上限で頭打ちになる。
        HEARTBEAT_INTERVAL = 5   # クライアント送信間隔（秒）
        MAX_INCREMENT = 10       # 1ハートビートあたりの加算上限（中断からの復帰時のスパイクを抑止）
        if progress.last_heartbeat_at is not None:
            elapsed = (now - progress.last_heartbeat_at).total_seconds()
        else:
            elapsed = HEARTBEAT_INTERVAL  # 初回は想定間隔ぶんだけ加算
        increment = int(round(max(0, min(elapsed, MAX_INCREMENT))))
        progress.actual_watch_seconds = (progress.actual_watch_seconds or 0) + increment
        enrollment.total_study_seconds = (enrollment.total_study_seconds or 0) + increment
    progress.last_heartbeat_at = now
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/courses/<int:course_id>/lessons/<int:lesson_id>/complete', methods=['POST'])
@login_required
def complete_lesson(course_id, lesson_id):
    """動画視聴完了 or 手動完了。実測視聴秒数を記録"""
    data = request.get_json(silent=True) or {}
    final_seconds = int(data.get('watch_seconds', 0))

    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first_or_404()

    # 未視聴制御: 直前レッスンが未完了なら完了処理を拒否（API直叩き対策）
    course = Course.query.get_or_404(course_id)
    completed_ids = {lp.lesson_id for lp in enrollment.lesson_progress if lp.is_completed}
    if lesson_id not in compute_unlocked_lesson_ids(course, completed_ids):
        return jsonify({'ok': False, 'error': '前のチャプターが未完了です'}), 403

    progress = LessonProgress.query.filter_by(
        enrollment_id=enrollment.id, lesson_id=lesson_id).first()
    if not progress:
        progress = LessonProgress(
            enrollment_id=enrollment.id,
            lesson_id=lesson_id,
            started_at=datetime.utcnow()
        )
        db.session.add(progress)

    if not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
        # ハートビートで積算した値より完了時点の秒数の方が大きければ更新。
        # 改ざん防止: クライアント申告値は動画長を上限にして水増しを防ぐ。
        lesson = Lesson.query.filter_by(id=lesson_id, course_id=course_id).first()
        cap = (lesson.duration_seconds or 0) if lesson else 0
        capped_final = min(final_seconds, cap) if cap > 0 else final_seconds
        if capped_final > (progress.actual_watch_seconds or 0):
            diff = capped_final - (progress.actual_watch_seconds or 0)
            progress.actual_watch_seconds = capped_final
            enrollment.total_study_seconds = (enrollment.total_study_seconds or 0) + diff

        log = StudyLog(
            user_id=current_user.id,
            course_id=course_id,
            lesson_id=lesson_id,
            login_at=progress.started_at or datetime.utcnow(),
            logout_at=datetime.utcnow(),
            duration_seconds=progress.actual_watch_seconds or 0,
            ip_address=request.remote_addr
        )
        db.session.add(log)

        # 進捗率をDBに保存（完了レッスン数 / 総レッスン数）
        total_lessons = len(course.lessons)
        done = len(completed_ids | {lesson_id})
        enrollment.progress_percent = int(done / total_lessons * 100) if total_lessons else 0
        db.session.commit()

    return jsonify({'ok': True, 'total_seconds': enrollment.total_study_seconds,
                    'progress_percent': enrollment.progress_percent})


@app.route('/courses/<int:course_id>/quiz/submit', methods=['POST'])
@login_required
def submit_quiz(course_id):
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first_or_404()
    quiz = Quiz.query.filter_by(course_id=course_id).first_or_404()
    questions = quiz.questions
    correct = 0
    answers = {}
    for q in questions:
        answer = request.form.get(f'q_{q.id}', '')
        answers[str(q.id)] = answer
        if answer.upper() == (q.correct_answer or '').upper():
            correct += 1
    score = int(correct / len(questions) * 100) if questions else 0

    # 解答履歴を全保存（改ざん防止: 既存レコードは変更せず追記のみ）
    db.session.add(QuizAttempt(
        user_id=current_user.id,
        course_id=course_id,
        quiz_id=quiz.id,
        score=score,
        answers_json=json.dumps(answers, ensure_ascii=False),
        ip_address=request.remote_addr
    ))

    enrollment.quiz_attempts += 1
    if enrollment.quiz_score is None or score > enrollment.quiz_score:
        enrollment.quiz_score = score

    course = Course.query.get(course_id)
    completed_lessons = LessonProgress.query.filter_by(
        enrollment_id=enrollment.id, is_completed=True).count()
    # レッスンが1本以上あり、全レッスン完了かつ合格点以上のときのみ修了。
    # （レッスン0本コースが 0==0 で即修了になる不具合を防止）
    if (len(course.lessons) > 0
            and score >= course.pass_score
            and completed_lessons == len(course.lessons)):
        enrollment.status = 'completed'
        enrollment.completed_at = datetime.utcnow()

    db.session.commit()
    return render_template('quiz_result.html', course=course, score=score,
                           correct=correct, total=len(questions), enrollment=enrollment)


# ===== 証明書・記録出力 =====

@app.route('/courses/<int:course_id>/course_certificate')
@login_required
def course_certificate(course_id):
    """コース全レッスン完了時の修了証"""
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first_or_404()
    course = Course.query.get_or_404(course_id)
    done = {lp.lesson_id for lp in enrollment.lesson_progress if lp.is_completed}
    if any(l.id not in done for l in course.lessons):
        flash('コースの全レッスンを完了していません', 'warning')
        return redirect(url_for('study_course', course_id=course_id))
    pdf = generate_course_certificate_pdf(current_user, course, enrollment)
    fname = f'修了証_{current_user.full_name or current_user.username}_{course.title}.pdf'
    return send_file(pdf, download_name=fname, as_attachment=True, mimetype='application/pdf')


@app.route('/courses/<int:course_id>/curriculum_certificate')
@login_required
def curriculum_certificate(course_id):
    """カリキュラム（同カテゴリ全コース）完了時の修了証"""
    course = Course.query.get_or_404(course_id)
    curr_courses = Course.query.filter_by(category=course.category).all()
    for cc in curr_courses:
        enr = Enrollment.query.filter_by(user_id=current_user.id, course_id=cc.id).first()
        if not enr:
            flash('カリキュラムの全コースを完了していません', 'warning')
            return redirect(url_for('study_course', course_id=course_id))
        done = {lp.lesson_id for lp in enr.lesson_progress if lp.is_completed}
        if any(l.id not in done for l in cc.lessons):
            flash('カリキュラムの全コースを完了していません', 'warning')
            return redirect(url_for('study_course', course_id=course_id))
    pdf = generate_curriculum_certificate_pdf(current_user, course.category, curr_courses)
    fname = f'修了証_{current_user.full_name or current_user.username}_{course.category}.pdf'
    return send_file(pdf, download_name=fname, as_attachment=True, mimetype='application/pdf')


@app.route('/courses/<int:course_id>/certificate')
@login_required
def download_certificate(course_id):
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first_or_404()
    if enrollment.status != 'completed':
        flash('コースを修了していません', 'warning')
        return redirect(url_for('study_course', course_id=course_id))
    course = Course.query.get(course_id)
    pdf = generate_certificate_pdf(current_user, course, enrollment)
    return send_file(pdf,
                     download_name=f'修了証_{current_user.full_name}_{course.title}.pdf',
                     as_attachment=True, mimetype='application/pdf')


@app.route('/admin/courses/<int:course_id>/report')
@login_required
def course_report(course_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    enrollments = (db.session.query(Enrollment, User)
                   .join(User, Enrollment.user_id == User.id)
                   .filter(Enrollment.course_id == course_id).all())
    return render_template('course_report.html', course=course, enrollments=enrollments)


@app.route('/admin/courses/<int:course_id>/export/csv')
@login_required
def export_csv(course_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    enrollments = (db.session.query(Enrollment, User)
                   .join(User, Enrollment.user_id == User.id)
                   .filter(Enrollment.course_id == course_id).all())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['社員番号', '氏名', '部署', '雇用形態', '受講開始日', '受講完了日',
                     '実視聴時間（秒）', '実視聴時間（時間）', 'テスト得点', '受験回数', '修了状況'])
    for enrollment, user in enrollments:
        writer.writerow([
            user.employee_id or '',
            user.full_name or user.username,
            user.department or '',
            user.employment_type or '',
            enrollment.started_at.strftime('%Y/%m/%d') if enrollment.started_at else '',
            enrollment.completed_at.strftime('%Y/%m/%d') if enrollment.completed_at else '',
            enrollment.total_study_seconds or 0,
            round((enrollment.total_study_seconds or 0) / 3600, 2),
            enrollment.quiz_score if enrollment.quiz_score is not None else '',
            enrollment.quiz_attempts,
            '修了' if enrollment.status == 'completed' else '受講中' if enrollment.status == 'in_progress' else '未開始'
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        download_name=f'訓練実施記録_{course.title}.csv',
        as_attachment=True, mimetype='text/csv; charset=utf-8-sig'
    )


@app.route('/admin/courses/<int:course_id>/export/pdf')
@login_required
def export_training_record_pdf(course_id):
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    enrollments = (db.session.query(Enrollment, User)
                   .join(User, Enrollment.user_id == User.id)
                   .filter(Enrollment.course_id == course_id).all())
    pdf = generate_training_record_pdf(course, enrollments)
    return send_file(pdf, download_name=f'訓練実施記録_{course.title}.pdf',
                     as_attachment=True, mimetype='application/pdf')


@app.route('/admin/logs')
@login_required
def admin_logs():
    """受講ログ一覧（労働局提出用）"""
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course_id = request.args.get('course_id', type=int)
    user_id = request.args.get('user_id', type=int)

    query = (db.session.query(StudyLog, User, Course, Lesson)
             .join(User, StudyLog.user_id == User.id)
             .join(Course, StudyLog.course_id == Course.id)
             .outerjoin(Lesson, StudyLog.lesson_id == Lesson.id))
    if course_id:
        query = query.filter(StudyLog.course_id == course_id)
    if user_id:
        query = query.filter(StudyLog.user_id == user_id)
    logs = query.order_by(StudyLog.login_at.desc()).limit(500).all()

    courses = Course.query.order_by(Course.title).all()
    users = User.query.filter_by(role='employee').order_by(User.full_name).all()
    return render_template('admin_logs.html', logs=logs, courses=courses, users=users,
                           selected_course=course_id, selected_user=user_id)


@app.route('/admin/logs/export/csv')
@login_required
def export_full_logs_csv():
    """全受講ログをCSV出力（秒単位）"""
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course_id = request.args.get('course_id', type=int)

    query = (db.session.query(StudyLog, User, Course, Lesson)
             .join(User, StudyLog.user_id == User.id)
             .join(Course, StudyLog.course_id == Course.id)
             .outerjoin(Lesson, StudyLog.lesson_id == Lesson.id))
    if course_id:
        query = query.filter(StudyLog.course_id == course_id)
    logs = query.order_by(StudyLog.login_at.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ログID', '社員番号', '氏名', '部署', '雇用形態',
                     'コース名', '訓練種別', 'レッスン名',
                     '視聴開始日時', '視聴終了日時', '視聴時間（秒）', '視聴時間（時間）',
                     'IPアドレス'])
    for log, user, course, lesson in logs:
        writer.writerow([
            log.id,
            user.employee_id or '',
            user.full_name or user.username,
            user.department or '',
            user.employment_type or '',
            course.title,
            course.training_type,
            lesson.title if lesson else '',
            log.login_at.strftime('%Y/%m/%d %H:%M:%S') if log.login_at else '',
            log.logout_at.strftime('%Y/%m/%d %H:%M:%S') if log.logout_at else '',
            log.duration_seconds or 0,
            round((log.duration_seconds or 0) / 3600, 4),
            log.ip_address or ''
        ])
    output.seek(0)
    filename = f'受講ログ_{datetime.now().strftime("%Y%m%d")}.csv'
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        download_name=filename,
        as_attachment=True, mimetype='text/csv; charset=utf-8-sig'
    )


@app.route('/admin/logs/login/export/csv')
@login_required
def export_login_sessions_csv():
    """ログイン/ログアウト証跡をCSV出力（秒単位・実施期間の整合性証明用）"""
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    user_id = request.args.get('user_id', type=int)

    query = (db.session.query(LoginSession, User)
             .join(User, LoginSession.user_id == User.id))
    if user_id:
        query = query.filter(LoginSession.user_id == user_id)
    sessions = query.order_by(LoginSession.login_at.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ログID', '社員番号', '氏名', '部署',
                     'ログイン日時', 'ログアウト日時', '滞在時間（秒）',
                     '終了区分', 'IPアドレス'])
    reason_map = {'logout': '通常ログアウト', 'forced': '別端末ログインによる終了'}
    for s, user in sessions:
        if s.login_at and s.logout_at:
            stay_seconds = int((s.logout_at - s.login_at).total_seconds())
        else:
            stay_seconds = ''
        writer.writerow([
            s.id,
            user.employee_id or '',
            user.full_name or user.username,
            user.department or '',
            s.login_at.strftime('%Y/%m/%d %H:%M:%S') if s.login_at else '',
            s.logout_at.strftime('%Y/%m/%d %H:%M:%S') if s.logout_at else '（未ログアウト）',
            stay_seconds,
            reason_map.get(s.logout_reason, ''),
            s.ip_address or ''
        ])
    output.seek(0)
    filename = f'ログイン証跡_{datetime.now().strftime("%Y%m%d")}.csv'
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        download_name=filename,
        as_attachment=True, mimetype='text/csv; charset=utf-8-sig'
    )


@app.route('/admin/courses/<int:course_id>/quiz-history')
@login_required
def admin_quiz_history(course_id):
    """テスト解答履歴"""
    if current_user.role != 'skillgrowth':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    quiz = Quiz.query.filter_by(course_id=course_id).first()
    attempts = []
    if quiz:
        attempts = (db.session.query(QuizAttempt, User)
                    .join(User, QuizAttempt.user_id == User.id)
                    .filter(QuizAttempt.quiz_id == quiz.id)
                    .order_by(QuizAttempt.attempted_at.desc()).all())
    return render_template('admin_quiz_history.html',
                           course=course, quiz=quiz, attempts=attempts)


# ===== PDF生成 =====

_JP_FONTS_REGISTERED = False

def _ensure_jp_fonts():
    global _JP_FONTS_REGISTERED
    if _JP_FONTS_REGISTERED:
        return
    candidates = [
        ('JpMincho', r'C:\Windows\Fonts\yumin.ttf', None),
        ('JpMincho', r'C:\Windows\Fonts\msmincho.ttc', 0),
        ('JpGothic', r'C:\Windows\Fonts\YuGothR.ttc', 0),
        ('JpGothic', r'C:\Windows\Fonts\msgothic.ttc', 0),
    ]
    for name, path, idx in candidates:
        try:
            kw = {'subfontIndex': idx} if idx is not None else {}
            pdfmetrics.registerFont(TTFont(name, path, **kw))
        except Exception:
            pass
    _JP_FONTS_REGISTERED = True


def generate_lesson_certificate_pdf(user, course, lesson, progress):
    """動画1本完了修了証"""
    total_sec = lesson.duration_seconds or (lesson.duration_minutes or 0) * 60
    completed_str = (progress.completed_at or datetime.utcnow()).strftime('%Y年%m月%d日')
    return _build_certificate_canvas(
        title_label='修了証',
        curriculum=course.category or course.title,
        course_title=course.title,
        lesson_title=lesson.title,
        total_sec=total_sec,
        user_name=user.full_name or user.username,
        completed_str=completed_str,
    )


def _build_certificate_canvas(title_label, curriculum, course_title, lesson_title,
                               total_sec, user_name, completed_str):
    """共通の修了証キャンバスを生成して返す"""
    _ensure_jp_fonts()
    MINCHO = 'JpMincho' if 'JpMincho' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    GOTHIC = 'JpGothic' if 'JpGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    GOLD  = HexColor('#B89A3E')
    BLACK = HexColor('#1a1a1a')
    GRAY  = HexColor('#555555')

    buf = io.BytesIO()
    W, H = A4
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('修了証')
    cx = W / 2

    # 二重金枠
    m1, m2 = 14*mm, 17.5*mm
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.rect(m1, m1, W - 2*m1, H - 2*m1)
    c.setLineWidth(0.5)
    c.rect(m2, m2, W - 2*m2, H - 2*m2)

    def hline(y, width_mm=100, lw=0.6):
        c.setStrokeColor(GOLD)
        c.setLineWidth(lw)
        half = (width_mm * mm) / 2
        c.line(cx - half, y, cx + half, y)

    # 修 了 証
    c.setFillColor(BLACK)
    c.setFont(MINCHO, 32)
    c.drawCentredString(cx, H - 55*mm, '修　了　証')
    hline(H - 67*mm, 60)

    # 講座名ブロック
    y = H - 88*mm
    c.setFillColor(GRAY)
    c.setFont(GOTHIC, 9)
    c.drawCentredString(cx, y, '講座名')

    c.setFillColor(BLACK)
    c.setFont(GOTHIC, 20)
    c.drawCentredString(cx, H - 103*mm, curriculum)

    # コース名（あれば）
    sub_y = H - 117*mm
    if course_title:
        c.setFont(GOTHIC, 13)
        c.setFillColor(GRAY)
        c.drawCentredString(cx, sub_y, course_title)
        sub_y -= 12*mm

    # 動画タイトル（あれば）
    if lesson_title:
        c.setFont(GOTHIC, 11)
        c.setFillColor(GRAY)
        c.drawCentredString(cx, sub_y, lesson_title)
        sub_y -= 12*mm

    # 標準学習時間
    h_val = total_sec // 3600
    m_val = (total_sec % 3600) // 60
    s_val = total_sec % 60
    if h_val > 0:
        time_str = f'（標準学習時間　{h_val}時間{m_val}分{s_val}秒）'
    else:
        time_str = f'（標準学習時間　{m_val}分{s_val}秒）'
    c.setFont(MINCHO, 11)
    c.setFillColor(BLACK)
    c.drawCentredString(cx, sub_y, time_str)

    line_y = sub_y - 13*mm
    hline(line_y, 120, lw=0.8)

    # 受講者ブロック
    c.setFillColor(GRAY)
    c.setFont(GOTHIC, 9)
    c.drawCentredString(cx, line_y - 20*mm, '受講者')
    c.setFillColor(BLACK)
    c.setFont(MINCHO, 26)
    c.drawCentredString(cx, line_y - 35*mm, user_name + '　殿')
    hline(line_y - 49*mm, 120, lw=0.8)

    # 本文
    body_y = line_y - 79*mm
    c.setFont(MINCHO, 12)
    c.drawCentredString(cx, body_y, 'あなたは頭書の講座における所定の課程を修了されたため、')
    c.drawCentredString(cx, body_y - 14*mm, 'ここにその修了を証します。')

    # 発行情報
    info_y = body_y - 44*mm
    info_x = cx + 20*mm
    c.setFont(MINCHO, 11)
    c.drawCentredString(info_x, info_y, completed_str)
    c.drawCentredString(info_x, info_y - 13*mm, 'Skill Growth 合同会社')
    c.drawCentredString(info_x, info_y - 26*mm, '代表社員　紙谷正平')

    c.save()
    buf.seek(0)
    return buf


def generate_course_certificate_pdf(user, course, enrollment):
    """コース全レッスン完了修了証"""
    total_sec = sum(l.duration_seconds or (l.duration_minutes or 0) * 60 for l in course.lessons)
    completed_str = (enrollment.completed_at or datetime.utcnow()).strftime('%Y年%m月%d日')
    return _build_certificate_canvas(
        title_label='修了証',
        curriculum=course.category or course.title,
        course_title=course.title,
        lesson_title=None,
        total_sec=total_sec,
        user_name=user.full_name or user.username,
        completed_str=completed_str,
    )


def generate_curriculum_certificate_pdf(user, curriculum_name, courses):
    """カリキュラム（全コース）完了修了証"""
    total_sec = sum(
        sum(l.duration_seconds or (l.duration_minutes or 0) * 60 for l in c.lessons)
        for c in courses
    )
    return _build_certificate_canvas(
        title_label='修了証',
        curriculum=curriculum_name,
        course_title=None,
        lesson_title=None,
        total_sec=total_sec,
        user_name=user.full_name or user.username,
        completed_str=datetime.utcnow().strftime('%Y年%m月%d日'),
    )


def generate_certificate_pdf(user, course, enrollment):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    story = []
    # 日本語フォントを登録し、和文はゴシックで描画（未登録環境ではHelveticaにフォールバック）
    _ensure_jp_fonts()
    GOTHIC = 'JpGothic' if 'JpGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    T = lambda name, **kw: ParagraphStyle(name, fontName=GOTHIC, **kw)
    TB = lambda name, **kw: ParagraphStyle(name, fontName=GOTHIC, **kw)

    story.append(Spacer(1, 30*mm))
    # 英字タイトルはHelvetica-Boldのままで可
    story.append(Paragraph("CERTIFICATE OF COMPLETION",
                           ParagraphStyle('t1', fontName='Helvetica-Bold', fontSize=22, alignment=1, spaceAfter=8)))
    story.append(Paragraph("訓練修了証", TB('t2', fontSize=20, alignment=1, spaceAfter=20)))
    story.append(Paragraph(f"氏名: {user.full_name or user.username}", TB('l', fontSize=14, alignment=1, spaceAfter=6)))
    story.append(Paragraph(f"社員番号: {user.employee_id or '-'}", T('b', fontSize=12, alignment=1, spaceAfter=4)))
    story.append(Paragraph(f"部署: {user.department or '-'}", T('b2', fontSize=12, alignment=1, spaceAfter=16)))
    story.append(Paragraph(f"訓練名: {course.title}", TB('l2', fontSize=14, alignment=1, spaceAfter=6)))
    story.append(Paragraph(f"訓練種別: {course.training_type}", T('b3', fontSize=12, alignment=1, spaceAfter=4)))
    story.append(Paragraph(f"規定訓練時間: {course.total_hours}時間", T('b4', fontSize=12, alignment=1, spaceAfter=4)))
    study_h = round((enrollment.total_study_seconds or 0) / 3600, 1)
    story.append(Paragraph(f"実際の視聴時間: {study_h}時間", T('b5', fontSize=12, alignment=1, spaceAfter=4)))
    period = (f"{enrollment.started_at.strftime('%Y年%m月%d日') if enrollment.started_at else '-'}"
              f" ～ {enrollment.completed_at.strftime('%Y年%m月%d日') if enrollment.completed_at else '-'}")
    story.append(Paragraph(f"受講期間: {period}", T('b6', fontSize=12, alignment=1, spaceAfter=4)))
    if enrollment.quiz_score is not None:
        story.append(Paragraph(f"理解度テスト最高点: {enrollment.quiz_score}点", T('b7', fontSize=12, alignment=1, spaceAfter=16)))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("上記の者は、上記訓練を修了したことを証明します。",
                            T('cert', fontSize=12, alignment=1, spaceAfter=8)))
    story.append(Paragraph(f"発行日: {datetime.now().strftime('%Y年%m月%d日')}",
                            T('date', fontSize=12, alignment=1)))
    doc.build(story)
    buf.seek(0)
    return buf


def generate_training_record_pdf(course, enrollments):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=12*mm, leftMargin=12*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    story = []
    # 日本語フォントを登録し、見出し・本文・表を和文ゴシックで描画
    _ensure_jp_fonts()
    GOTHIC = 'JpGothic' if 'JpGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    story.append(Paragraph("訓練実施記録", ParagraphStyle(
        'h1', fontSize=15, alignment=1, fontName=GOTHIC, spaceAfter=4)))
    story.append(Paragraph(
        f"訓練名: {course.title}　訓練種別: {course.training_type}　"
        f"訓練時間: {course.total_hours}h　合格点: {course.pass_score}点　"
        f"出力日: {datetime.now().strftime('%Y/%m/%d')}",
        ParagraphStyle('meta', fontName=GOTHIC, fontSize=9)))
    story.append(Spacer(1, 4*mm))

    data = [['氏名', '社員番号', '部署', '雇用形態', '開始日', '修了日',
             '視聴時間(h)', 'テスト', '受験数', '状況']]
    for enrollment, user in enrollments:
        data.append([
            user.full_name or user.username,
            user.employee_id or '-',
            user.department or '-',
            user.employment_type or '-',
            enrollment.started_at.strftime('%Y/%m/%d') if enrollment.started_at else '-',
            enrollment.completed_at.strftime('%Y/%m/%d') if enrollment.completed_at else '-',
            f"{round((enrollment.total_study_seconds or 0)/3600, 2)}",
            f"{enrollment.quiz_score}点" if enrollment.quiz_score is not None else '-',
            str(enrollment.quiz_attempts),
            '修了' if enrollment.status == 'completed' else '受講中' if enrollment.status == 'in_progress' else '未開始'
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), GOTHIC),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(table)
    doc.build(story)
    buf.seek(0)
    return buf


# ===== 初期データ =====

def create_initial_data():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            # 初期パスワードは環境変数で上書き可。初回ログイン時にパスワード変更を強制する。
            init_pw = os.environ.get('LMS_ADMIN_PASSWORD', 'admin123')
            db.session.add(User(
                username='admin', email='admin@example.com',
                password_hash=generate_password_hash(init_pw),
                full_name='管理者', role='skillgrowth',
                force_password_change=True
            ))
            db.session.commit()
            print(f'管理者アカウント作成: admin / {init_pw}（初回ログイン時にパスワード変更が必要です）')


if __name__ == '__main__':
    create_initial_data()
    # debug は既定で無効。開発時のみ環境変数 FLASK_DEBUG=1 で有効化する。
    debug = os.environ.get('FLASK_DEBUG') == '1'
    host = os.environ.get('LMS_HOST', '127.0.0.1')
    port = int(os.environ.get('LMS_PORT', '5000'))
    app.run(debug=debug, host=host, port=port)
