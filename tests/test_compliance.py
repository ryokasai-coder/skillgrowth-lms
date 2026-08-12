"""助成金対応の要点機能に対する回帰テスト。

- 未視聴制御（サーバ側の解放判定・完了API 403・heartbeat 403）
- 受講時間の水増し防止（heartbeat連打）
- コース設定の新フィールド保存
- ログイン/ログアウト証跡
- レッスン0本コースの即修了バグ
- 帳票PDFの日本語フォント埋め込み
"""
from datetime import datetime

from conftest import login
from app import (app as flask_app, db, compute_unlocked_lesson_ids,
                 Course, Lesson, User, Enrollment, LessonProgress, LoginSession)
from werkzeug.security import generate_password_hash


# ---------- 未視聴制御ロジック ----------

def test_gating_disabled_all_unlocked(seed_course):
    """運用方針で未視聴制御はOFF。全レッスンが解放される。"""
    import app as appmod
    assert appmod.LESSON_GATING_ENABLED is False
    with flask_app.app_context():
        course = db.session.get(Course, seed_course['course_id'])
        ids = set(seed_course['lesson_ids'])
        assert compute_unlocked_lesson_ids(course, set()) == ids  # 何も完了せずとも全解放


def test_gating_logic_when_enabled(seed_course):
    """将来ONにした場合の順次解放ロジックの検証（フラグを一時的に有効化）。"""
    import app as appmod
    orig = appmod.LESSON_GATING_ENABLED
    appmod.LESSON_GATING_ENABLED = True
    try:
        with flask_app.app_context():
            course = db.session.get(Course, seed_course['course_id'])
            ids = seed_course['lesson_ids']
            u0 = compute_unlocked_lesson_ids(course, set())
            assert ids[0] in u0 and ids[1] not in u0
            u1 = compute_unlocked_lesson_ids(course, {ids[0]})
            assert ids[1] in u1 and ids[2] not in u1
    finally:
        appmod.LESSON_GATING_ENABLED = orig


def test_any_lesson_completable_when_gating_off(client, seed_course):
    """ロックOFFなので、前レッスン未完了でも任意のレッスンを完了/再生できる。"""
    cid = seed_course['course_id']
    l2, l3 = seed_course['lesson_ids'][1], seed_course['lesson_ids'][2]
    login(client)
    assert client.post(f'/courses/{cid}/lessons/{l3}/heartbeat', json={'position_seconds': 5}).status_code == 200
    assert client.post(f'/courses/{cid}/lessons/{l2}/complete', json={'watch_seconds': 0}).status_code == 200


# ---------- 受講時間の水増し防止 ----------

def test_heartbeat_burst_does_not_inflate(client, seed_course):
    cid = seed_course['course_id']
    l1 = seed_course['lesson_ids'][0]
    login(client)
    for i in range(5):  # 間髪入れず5連打（申告どおりなら+25秒相当）
        client.post(f'/courses/{cid}/lessons/{l1}/heartbeat', json={'position_seconds': i})
    with flask_app.app_context():
        enr = Enrollment.query.filter_by(course_id=cid).first()
        # 初回5秒 + 実経過ほぼ0 なので、上限(10秒)以内に収まる
        assert (enr.total_study_seconds or 0) <= 10


def test_complete_watch_seconds_capped_by_video_length(client, seed_course):
    cid = seed_course['course_id']
    l1 = seed_course['lesson_ids'][0]  # duration_seconds=600
    login(client)
    client.post(f'/courses/{cid}/lessons/{l1}/complete', json={'watch_seconds': 999999})
    with flask_app.app_context():
        lp = LessonProgress.query.filter_by(lesson_id=l1).first()
        assert lp.actual_watch_seconds <= 600  # 動画長で頭打ち


# ---------- コース設定の新フィールド保存 ----------

def test_course_creation_persists_new_fields(client):
    with flask_app.app_context():
        db.session.add(User(username='admin', email='a@a.com',
                            password_hash=generate_password_hash('adminpass'),
                            role='skillgrowth', full_name='管理者'))
        db.session.commit()
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})
    client.post('/admin/courses/new', data={
        'title': '新フィールドコース', 'description': '', 'category': 'C',
        'training_type': '専門知識習得コース', 'total_hours': '7.5', 'pass_score': '85'})
    with flask_app.app_context():
        c = Course.query.filter_by(title='新フィールドコース').first()
        assert c is not None
        assert c.training_type == '専門知識習得コース'
        assert abs(c.total_hours - 7.5) < 0.01
        assert c.pass_score == 85


# ---------- ログイン/ログアウト証跡 ----------

def test_login_logout_leaves_trail(client, seed_course):
    login(client)
    with flask_app.app_context():
        ls = LoginSession.query.order_by(LoginSession.id.desc()).first()
        assert ls is not None and ls.logout_at is None
    client.get('/logout')
    with flask_app.app_context():
        ls = LoginSession.query.order_by(LoginSession.id.desc()).first()
        assert ls.logout_at is not None and ls.logout_reason == 'logout'


# ---------- レッスン0本コースの即修了バグ ----------

def test_zero_lesson_course_not_auto_completed(client):
    with flask_app.app_context():
        u = User(username='emp0', email='e0@a.com',
                 password_hash=generate_password_hash('pass1234'), role='employee', full_name='零')
        c = Course(title='空コース', pass_score=80, is_published=True)  # レッスン0本
        db.session.add_all([u, c]); db.session.flush()
        from app import Quiz, Question
        q = Quiz(course_id=c.id, title='テスト'); db.session.add(q); db.session.flush()
        db.session.add(Question(quiz_id=q.id, question_text='Q', option_a='a', option_b='b',
                                correct_answer='A', order=1))
        db.session.add(Enrollment(user_id=u.id, course_id=c.id))
        db.session.commit()
        cid, qid = c.id, q.id
        first_q = Question.query.filter_by(quiz_id=qid).first().id
    login(client, 'emp0', 'pass1234')
    client.post(f'/courses/{cid}/quiz/submit', data={f'q_{first_q}': 'A'})
    with flask_app.app_context():
        enr = Enrollment.query.filter_by(course_id=cid).first()
        assert enr.status != 'completed'  # レッスン0本なので修了しない


# ---------- 帳票PDFの日本語フォント埋め込み ----------

def test_certificate_pdf_embeds_japanese_font(seed_course):
    from app import generate_certificate_pdf
    with flask_app.app_context():
        course = db.session.get(Course, seed_course['course_id'])
        user = db.session.get(User, seed_course['user_id'])
        enr = Enrollment.query.filter_by(course_id=course.id).first()
        enr.started_at = datetime(2026, 7, 1)
        enr.completed_at = datetime(2026, 7, 20)
        enr.total_study_seconds = 3600
        pdf = generate_certificate_pdf(user, course, enr).read()
    # 有効なPDFであること
    assert pdf.startswith(b'%PDF')
    # 日本語フォントを埋め込むとサブセットフォントぶんサイズが跳ねる（Helvetica単体だと約2KB＝文字化け状態）。
    # このサイズ閾値が、修了証の日本語が豆腐(■)に戻る回帰を検知する。
    assert len(pdf) > 20000, f'PDFが小さすぎ({len(pdf)}B)＝日本語フォント未埋め込みの疑い'
