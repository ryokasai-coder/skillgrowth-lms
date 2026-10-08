"""heartbeatの二重計上・空打ち防止。

- ユーザー単位の直前heartbeat時刻で、複数レッスン並行再生でも合計加算が実経過時間を超えない
- 加算量は再生位置(position)の前進量以下（positionが進まない空打ちは加算0）
"""
from datetime import datetime, timedelta

from conftest import login
from app import app as flask_app, db, User, Enrollment, LessonProgress


def _hb(client, cid, lid, pos):
    r = client.post(f'/courses/{cid}/lessons/{lid}/heartbeat', json={'position_seconds': pos})
    assert r.status_code == 200
    return r


def _set_last_hb(uid, seconds_ago, cid=None, lid=None):
    """直前heartbeatが seconds_ago 秒前だった状態にする（実時間を待たずに再現）。"""
    t = datetime.utcnow() - timedelta(seconds=seconds_ago)
    with flask_app.app_context():
        db.session.get(User, uid).last_heartbeat_at = t
        for lp in LessonProgress.query.all():
            lp.last_heartbeat_at = t
        db.session.commit()


def _total(cid):
    with flask_app.app_context():
        return Enrollment.query.filter_by(course_id=cid).first().total_study_seconds or 0


def _watch(lid):
    with flask_app.app_context():
        lp = LessonProgress.query.filter_by(lesson_id=lid).first()
        return (lp.actual_watch_seconds or 0) if lp else 0


def test_normal_playback_still_accumulates(client, seed_course):
    cid, uid, l1 = seed_course['course_id'], seed_course['user_id'], seed_course['lesson_ids'][0]
    login(client)
    _hb(client, cid, l1, 5)      # 初回は想定間隔ぶん(5秒)
    assert _watch(l1) == 5
    _set_last_hb(uid, 5)
    _hb(client, cid, l1, 10)     # 5秒経過・位置も+5
    assert _watch(l1) == 10
    assert _total(cid) == 10


def test_no_position_advance_adds_nothing(client, seed_course):
    cid, uid, l1 = seed_course['course_id'], seed_course['user_id'], seed_course['lesson_ids'][0]
    login(client)
    _hb(client, cid, l1, 20)
    base = _watch(l1)
    for _ in range(3):
        _set_last_hb(uid, 5)     # 時間は経っているが位置は動いていない（空打ち）
        _hb(client, cid, l1, 20)
    assert _watch(l1) == base
    assert _total(cid) == base


def test_increment_limited_by_position_advance(client, seed_course):
    cid, uid, l1 = seed_course['course_id'], seed_course['user_id'], seed_course['lesson_ids'][0]
    login(client)
    _hb(client, cid, l1, 100)
    base = _watch(l1)
    _set_last_hb(uid, 10)        # 10秒経過したが位置は+2しか進んでいない
    _hb(client, cid, l1, 102)
    assert _watch(l1) == base + 2


def test_parallel_lessons_not_double_counted(client, seed_course):
    cid, uid = seed_course['course_id'], seed_course['user_id']
    l1, l2 = seed_course['lesson_ids'][:2]
    login(client)
    _hb(client, cid, l1, 5)
    _hb(client, cid, l2, 5)
    before = _total(cid)
    _set_last_hb(uid, 5)         # 実経過は5秒
    # 2レッスンを同時刻に並行再生しているふり（どちらも位置は+5）
    _hb(client, cid, l1, 10)
    _hb(client, cid, l2, 10)
    assert _total(cid) - before <= 5   # 合計は実経過時間(5秒)を超えない
    assert _total(cid) - before >= 0


def test_user_last_heartbeat_recorded(client, seed_course):
    cid, uid, l1 = seed_course['course_id'], seed_course['user_id'], seed_course['lesson_ids'][0]
    login(client)
    _hb(client, cid, l1, 5)
    with flask_app.app_context():
        assert db.session.get(User, uid).last_heartbeat_at is not None


def test_migrate_adds_user_last_heartbeat_at(tmp_path, monkeypatch):
    """migrate.py が既存DBに user.last_heartbeat_at を追加する（本番取り込み時の手順）。"""
    import sqlite3
    import migrate
    path = str(tmp_path / 'lms.db')
    from sqlalchemy import create_engine
    eng = create_engine('sqlite:///' + path.replace(chr(92), '/'))
    db.metadata.create_all(eng)
    eng.dispose()
    conn = sqlite3.connect(path)
    conn.execute('ALTER TABLE user DROP COLUMN last_heartbeat_at')
    conn.commit()
    conn.close()
    monkeypatch.setattr(migrate, 'DB_PATH', path)
    migrate.migrate()
    conn = sqlite3.connect(path)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(user)')]
    conn.close()
    assert 'last_heartbeat_at' in cols
