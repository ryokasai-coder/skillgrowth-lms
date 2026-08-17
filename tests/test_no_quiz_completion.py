"""テスト不要方針の検証: テストの無いコースは全レッスン視聴完了で修了扱いになること。"""
from conftest import login
from app import app as flask_app, db, Course, Lesson, User, Enrollment
from werkzeug.security import generate_password_hash


def _make_no_quiz_course():
    with flask_app.app_context():
        c = Course(title='テスト無しコース', category='研修',
                   training_type='eラーニング', total_hours=1.0,
                   is_published=True)
        db.session.add(c)
        db.session.flush()
        # テキストレッスン（video_url無し）= 手動完了。テスト(Quiz)は作らない。
        l1 = Lesson(course_id=c.id, title='L1', content='本文1', order=1)
        l2 = Lesson(course_id=c.id, title='L2', content='本文2', order=2)
        db.session.add_all([l1, l2])
        db.session.flush()
        u = User(username='emp', email='emp@example.com',
                 password_hash=generate_password_hash('pass1234'),
                 role='employee', full_name='検証太郎', employee_id='E999')
        db.session.add(u)
        db.session.flush()
        db.session.add(Enrollment(user_id=u.id, course_id=c.id))
        db.session.commit()
        return c.id, l1.id, l2.id


def test_no_quiz_course_completes_when_all_lessons_done(client):
    course_id, l1, l2 = _make_no_quiz_course()
    login(client)

    # 未修了の確認
    with flask_app.app_context():
        e = Enrollment.query.filter_by(course_id=course_id).first()
        assert e.status != 'completed'

    # 1本目→2本目の順に完了（未視聴ロックのため順序どおり）
    r1 = client.post(f'/courses/{course_id}/lessons/{l1}/complete', json={'watch_seconds': 0})
    r2 = client.post(f'/courses/{course_id}/lessons/{l2}/complete', json={'watch_seconds': 0})
    assert r1.status_code == 200, r1.data
    assert r2.status_code == 200, r2.data

    # 全レッスン完了で「修了」になっていること
    with flask_app.app_context():
        e = Enrollment.query.filter_by(course_id=course_id).first()
        assert e.status == 'completed', f'status={e.status}'
        assert e.completed_at is not None
        assert e.progress_percent == 100
