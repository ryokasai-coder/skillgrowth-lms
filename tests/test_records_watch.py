"""視聴時間は「サーバ実測」のみ（申告値の上乗せ廃止）。"""
from conftest import login, set_watched
from app import app as flask_app, db, LessonProgress, StudyLog, Enrollment


def test_complete_does_not_raise_measured_seconds(client, seed_course):
    """heartbeat実測100秒相当しかないのに watch_seconds=600 を送っても実測のまま。"""
    cid = seed_course['course_id']
    l1 = seed_course['lesson_ids'][0]
    login(client)
    set_watched(cid, l1, 100)
    with flask_app.app_context():
        enr = Enrollment.query.filter_by(course_id=cid).first()
        enr.total_study_seconds = 100
        db.session.commit()
    # 動画レッスンは実視聴9割未満だと完了拒否される。その場合も記録は変わらない。
    r = client.post(f'/courses/{cid}/lessons/{l1}/complete', json={'watch_seconds': 600})
    assert r.status_code == 403
    with flask_app.app_context():
        lp = LessonProgress.query.filter_by(lesson_id=l1).first()
        assert lp.actual_watch_seconds == 100
        assert Enrollment.query.filter_by(course_id=cid).first().total_study_seconds == 100


def test_complete_studylog_uses_measured_seconds(client, seed_course):
    cid = seed_course['course_id']
    l1 = seed_course['lesson_ids'][0]
    login(client)
    set_watched(cid, l1, 560)  # 9割(540)以上
    r = client.post(f'/courses/{cid}/lessons/{l1}/complete', json={'watch_seconds': 600})
    assert r.status_code == 200
    with flask_app.app_context():
        assert LessonProgress.query.filter_by(lesson_id=l1).first().actual_watch_seconds == 560
        assert StudyLog.query.filter_by(lesson_id=l1).first().duration_seconds == 560
