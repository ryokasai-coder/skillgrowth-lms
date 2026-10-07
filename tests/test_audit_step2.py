"""監査対応ステップ2: LMS情報の写し / 受講時間10時間以上の者の一覧表 / 既存出力の事業所フィルタ。"""
import csv
import io
from datetime import datetime

from conftest import login
from app import (app as flask_app, db, Company, User, Course, Lesson, Enrollment,
                 LessonProgress, StudyLog, LoginSession)
from werkzeug.security import generate_password_hash

H = 3600


def _bom_rows(resp):
    text = resp.data.decode('utf-8-sig')
    return list(csv.reader(io.StringIO(text)))


def _mk_user(username, role='employee', company=None, name=None, emp_id=None):
    u = User(username=username, email=username + '@x.com',
             password_hash=generate_password_hash('pass1234'),
             role=role, company_id=company.id if company else None,
             full_name=name or username, employee_id=emp_id)
    db.session.add(u)
    db.session.flush()
    return u


def _mk_course(title, lesson_secs, category='定額研修', sort_order=0):
    c = Course(title=title, category=category, training_type='eラーニング',
               is_published=True, sort_order=sort_order)
    db.session.add(c)
    db.session.flush()
    ls = []
    for i, s in enumerate(lesson_secs, 1):
        l = Lesson(course_id=c.id, title=f'{title}-L{i}', order=i, duration_seconds=s)
        db.session.add(l)
        ls.append(l)
    db.session.flush()
    return c, ls


def _complete(user, course, lessons, done_at, started_at=None, n_done=None):
    """受講を作り、先頭 n_done レッスンを done_at に完了。全完了なら修了。"""
    enr = Enrollment(user_id=user.id, course_id=course.id,
                     started_at=started_at or done_at, status='in_progress',
                     total_study_seconds=sum(l.duration_seconds for l in lessons))
    db.session.add(enr)
    db.session.flush()
    n = len(lessons) if n_done is None else n_done
    for l in lessons[:n]:
        db.session.add(LessonProgress(enrollment_id=enr.id, lesson_id=l.id,
                                      is_completed=True, completed_at=done_at,
                                      started_at=done_at))
    if n == len(lessons):
        enr.status = 'completed'
        enr.completed_at = done_at
    db.session.flush()
    return enr


def _world():
    """会社A(2名)・会社B(1名)・会社管理者。"""
    with flask_app.app_context():
        a = Company(name='A商事')
        b = Company(name='B工業')
        db.session.add_all([a, b])
        db.session.flush()
        _mk_user('sg', 'skillgrowth')
        _mk_user('caa', 'company_admin', a)
        _mk_user('cab', 'company_admin', b)
        pa = _mk_user('pa', company=a, name='甲野太郎', emp_id='A001')
        qa = _mk_user('qa', company=a, name='乙山花子', emp_id='A002')
        pb = _mk_user('pb', company=b, name='丙川次郎', emp_id='B001')
        c1, l1 = _mk_course('第1章', [6 * H], sort_order=1)
        c2, l2 = _mk_course('第2章', [3 * H], sort_order=2)
        c3, l3 = _mk_course('第3章', [2 * H], sort_order=3)
        # 甲野: 6h -> 9h -> 11h(第3章で到達)。第3章修了は UTC 10/7 16:30 = JST 10/8 01:30
        _complete(pa, c1, l1, datetime(2026, 9, 1, 3, 0))
        _complete(pa, c2, l2, datetime(2026, 9, 10, 3, 0))
        _complete(pa, c3, l3, datetime(2026, 10, 7, 16, 30))
        # 乙山: 6h + 3h59m = 9h59m
        c4, l4 = _mk_course('第4章', [3 * H + 59 * 60], sort_order=4)
        _complete(qa, c1, l1, datetime(2026, 9, 2, 3, 0))
        _complete(qa, c4, l4, datetime(2026, 9, 3, 3, 0))
        # 丙川(他社): 11h 到達
        _complete(pb, c1, l1, datetime(2026, 9, 5, 3, 0))
        _complete(pb, c2, l2, datetime(2026, 9, 6, 3, 0))
        _complete(pb, c3, l3, datetime(2026, 9, 7, 3, 0))
        db.session.commit()
        return {'a': a.id, 'b': b.id, 'pa': pa.id, 'qa': qa.id, 'pb': pb.id,
                'c1': c1.id, 'c2': c2.id}


# ---------- 10時間以上の者の一覧表 ----------

def test_ten_hours_picks_course_where_cumulative_crosses_10h(client):
    w = _world()
    login(client, 'sg')
    r = client.get(f'/audit/ten-hours/csv?company_id={w["a"]}')
    assert r.status_code == 200
    rows = _bom_rows(r)
    names = [row[2] for row in rows[1:]]
    assert names == ['甲野太郎']          # 9h59m の乙山は載らない・他社の丙川も載らない
    row = rows[1]
    assert row[3] == '2026/10/08'          # 累積10hを超えた第3章の修了日(JST)
    assert row[4] == '11:00:00'            # 修了講座の標準学習時間合計


def test_ten_hours_exactly_10h_counts(client):
    with flask_app.app_context():
        a = Company(name='A商事')
        db.session.add(a)
        db.session.flush()
        _mk_user('sg', 'skillgrowth')
        p = _mk_user('p', company=a, name='ちょうど', emp_id='1')
        c1, l1 = _mk_course('X1', [4 * H])
        c2, l2 = _mk_course('X2', [6 * H])
        _complete(p, c1, l1, datetime(2026, 9, 1, 3, 0))
        _complete(p, c2, l2, datetime(2026, 9, 2, 3, 0))
        db.session.commit()
        cid = a.id
    login(client, 'sg')
    rows = _bom_rows(client.get(f'/audit/ten-hours/csv?company_id={cid}'))
    assert len(rows) == 2 and rows[1][3] == '2026/09/02'


def test_ten_hours_incomplete_courses_not_counted(client):
    with flask_app.app_context():
        a = Company(name='A商事')
        db.session.add(a)
        db.session.flush()
        _mk_user('sg', 'skillgrowth')
        p = _mk_user('p', company=a, name='未修了', emp_id='1')
        c1, l1 = _mk_course('X1', [6 * H, 6 * H])
        _complete(p, c1, l1, datetime(2026, 9, 1, 3, 0), n_done=1)  # 途中
        db.session.commit()
        cid = a.id
    login(client, 'sg')
    rows = _bom_rows(client.get(f'/audit/ten-hours/csv?company_id={cid}'))
    assert len(rows) == 1  # ヘッダのみ


def test_ten_hours_period_filter(client):
    w = _world()
    login(client, 'sg')
    base = f'/audit/ten-hours/csv?company_id={w["a"]}'
    assert len(_bom_rows(client.get(base + '&from=2026-09-01&to=2026-10-31'))) == 2
    # 契約期間外（10/01より前）の修了は累積しない → 10月の修了だけでは誰も10時間に届かない
    assert len(_bom_rows(client.get(base + '&from=2026-10-01'))) == 1   # ヘッダーのみ
    # to=10/07 だと 10/08(JST) の修了は対象外 → 到達していない
    assert len(_bom_rows(client.get(base + '&to=2026-10-07'))) == 1


def test_ten_hours_requires_company_for_skillgrowth(client):
    _world()
    login(client, 'sg')
    assert client.get('/audit/ten-hours/csv').status_code == 400


def test_ten_hours_pdf(client):
    w = _world()
    login(client, 'sg')
    r = client.get(f'/audit/ten-hours/pdf?company_id={w["a"]}')
    assert r.status_code == 200
    assert r.data[:4] == b'%PDF'
    assert r.mimetype == 'application/pdf'


# ---------- 権限 ----------

def test_company_admin_own_company_default_and_forbidden_other(client):
    w = _world()
    login(client, 'caa')
    rows = _bom_rows(client.get('/audit/ten-hours/csv'))   # company_id 省略 → 自社
    assert [r[2] for r in rows[1:]] == ['甲野太郎']
    assert client.get(f'/audit/ten-hours/csv?company_id={w["a"]}').status_code == 200
    for path in ('ten-hours/csv', 'ten-hours/pdf', 'lms-copy/csv', 'lms-copy/pdf'):
        assert client.get(f'/audit/{path}?company_id={w["b"]}').status_code == 403
    # 他社の受講者を user_id で指定しても不可
    assert client.get(f'/audit/lms-copy/csv?user_id={w["pb"]}').status_code == 403


def test_employee_forbidden_and_anonymous_redirect(client):
    w = _world()
    assert client.get(f'/audit/lms-copy/csv?company_id={w["a"]}').status_code in (302, 401)
    login(client, 'pa')
    assert client.get(f'/audit/lms-copy/csv?company_id={w["a"]}').status_code == 403
    assert client.get(f'/audit/ten-hours/pdf?company_id={w["a"]}').status_code == 403


# ---------- LMS情報の写し ----------

def test_lms_copy_csv_rows_jst_progress(client):
    with flask_app.app_context():
        a = Company(name='A商事')
        db.session.add(a)
        db.session.flush()
        _mk_user('sg', 'skillgrowth')
        p = _mk_user('p', company=a, name='進捗花子', emp_id='E1')
        c, ls = _mk_course('第3章：文章業務の自動化', [1800, 1800, 1800], category='AI研修', sort_order=3)
        # 3レッスン中2つ完了 → 66.7% / 未修了
        enr = _complete(p, c, ls, datetime(2026, 10, 7, 16, 30),
                        started_at=datetime(2026, 10, 7, 0, 0), n_done=2)
        enr.total_study_seconds = 3725
        db.session.add(StudyLog(user_id=p.id, course_id=c.id, lesson_id=ls[0].id,
                                login_at=datetime(2026, 10, 7, 0, 5),
                                logout_at=datetime(2026, 10, 7, 17, 0),
                                duration_seconds=100))
        # 完了済みコース
        c2, ls2 = _mk_course('第1章', [3600], category='AI研修', sort_order=1)
        _complete(p, c2, ls2, datetime(2026, 10, 1, 3, 0))
        db.session.commit()
        cid = a.id
    login(client, 'sg')
    r = client.get(f'/audit/lms-copy/csv?company_id={cid}')
    assert r.status_code == 200
    assert r.data[:3] == b'\xef\xbb\xbf'
    rows = _bom_rows(r)
    assert rows[0] == ['事業所名', '社員番号', '氏名', '研修名', '講座名', '標準学習時間',
                       '受講開始日時(JST)', '受講終了日時(JST)', '受講時間数',
                       '進捗率', '修了日(JST)']
    first, second = rows[1], rows[2]      # sort_order順: 第1章 → 第3章
    assert first[4] == '第1章' and first[10] == '2026/10/01'
    assert first[5] == '1:00:00' and first[9] == '100.0%'
    assert second[0] == 'A商事' and second[1] == 'E1' and second[2] == '進捗花子'
    assert second[3] == 'AI研修'
    assert second[5] == '1:30:00'
    assert second[6] == '2026/10/07 09:00:00'     # UTC 00:00 -> JST 09:00
    assert second[7] == '2026/10/08 02:00:00'     # StudyLog最終 UTC 17:00 -> JST 02:00
    assert second[8] == '1:02:05'
    assert second[9] == '66.7%'
    assert second[10] == ''                         # 未修了は空


def test_lms_copy_no_other_company_and_user_filter(client):
    w = _world()
    login(client, 'sg')
    rows = _bom_rows(client.get(f'/audit/lms-copy/csv?company_id={w["a"]}'))
    assert {r[0] for r in rows[1:]} == {'A商事'}
    assert {r[2] for r in rows[1:]} == {'甲野太郎', '乙山花子'}
    rows = _bom_rows(client.get(f'/audit/lms-copy/csv?company_id={w["a"]}&user_id={w["pa"]}'))
    assert {r[2] for r in rows[1:]} == {'甲野太郎'}
    # 会社と受講者の不一致 -> 他社の個人情報は出ない
    rows = _bom_rows(client.get(f'/audit/lms-copy/csv?company_id={w["a"]}&user_id={w["pb"]}'))
    assert len(rows) == 1


def test_lms_copy_period_filter(client):
    w = _world()
    login(client, 'sg')
    rows = _bom_rows(client.get(
        f'/audit/lms-copy/csv?company_id={w["a"]}&user_id={w["pa"]}&from=2026-10-01&to=2026-10-31'))
    assert [r[4] for r in rows[1:]] == ['第3章']


def test_lms_copy_pdf_and_bad_date(client):
    w = _world()
    login(client, 'sg')
    r = client.get(f'/audit/lms-copy/pdf?company_id={w["a"]}')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    assert client.get('/audit/lms-copy/csv?from=2026-13-99').status_code == 400


def test_company_admin_lms_copy_pdf_own(client):
    _world()
    login(client, 'caa')
    r = client.get('/audit/lms-copy/pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'


# ---------- 既存出力の事業所フィルタ ----------

def test_existing_exports_company_filter(client):
    w = _world()
    with flask_app.app_context():
        for uid, cid in ((w['pa'], w['c1']), (w['pb'], w['c1'])):
            db.session.add(StudyLog(user_id=uid, course_id=cid,
                                    login_at=datetime(2026, 9, 1), duration_seconds=5))
            db.session.add(LoginSession(user_id=uid, login_at=datetime(2026, 9, 1)))
        db.session.commit()
    login(client, 'sg')
    allrows = _bom_rows(client.get('/admin/logs/export/csv'))
    assert {'甲野太郎', '丙川次郎'} <= {r[2] for r in allrows[1:]}
    rows = _bom_rows(client.get(f'/admin/logs/export/csv?company_id={w["a"]}'))
    assert {r[2] for r in rows[1:]} == {'甲野太郎'}
    rows = _bom_rows(client.get(f'/admin/logs/login/export/csv?company_id={w["b"]}'))
    assert {r[2] for r in rows[1:]} == {'丙川次郎'}
    rows = _bom_rows(client.get(f'/admin/courses/{w["c1"]}/export/csv?company_id={w["a"]}'))
    assert {r[1] for r in rows[1:]} == {'甲野太郎', '乙山花子'}
    r = client.get(f'/admin/courses/{w["c1"]}/export/pdf?company_id={w["b"]}')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'


# ---------- 画面 ----------

def test_ui_has_audit_forms(client):
    _world()
    login(client, 'sg')
    html = client.get('/admin/logs').data.decode()
    assert '/audit/lms-copy/csv' in html and '/audit/ten-hours/pdf' in html
    assert 'name="company_id"' in html
    client.get('/logout')
    login(client, 'caa')
    html = client.get('/ca/reports').data.decode()
    assert '/audit/lms-copy/pdf' in html and '/audit/ten-hours/csv' in html
