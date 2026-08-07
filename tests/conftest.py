"""pytest共通フィクスチャ。

本番DB（instance/lms.db）を汚さないよう、テスト用の一時SQLiteに隔離する。
app をインポートする前に LMS_DATABASE_URI を設定するのが要点。
"""
import os
import tempfile
import pytest

# ---- app インポート前に一時DBを指定（重要）----
_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix='.db')
os.close(_tmp_db_fd)
os.environ['LMS_DATABASE_URI'] = 'sqlite:///' + _tmp_db_path.replace('\\', '/')
os.environ.setdefault('LMS_SECRET_KEY', 'test-secret')

from app import (app as flask_app, db,  # noqa: E402
                 Company, User, Course, Lesson, Enrollment)
from werkzeug.security import generate_password_hash  # noqa: E402


@pytest.fixture(scope='session', autouse=True)
def _create_schema():
    with flask_app.app_context():
        db.create_all()
    yield
    try:
        os.remove(_tmp_db_path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _clean_tables():
    """各テスト前に全テーブルを空にして独立性を担保する。"""
    with flask_app.app_context():
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
    yield


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    return flask_app.test_client()


@pytest.fixture
def seed_course():
    """3レッスン（動画あり=duration設定済み）のコースと受講者を作る。"""
    with flask_app.app_context():
        c = Course(title='テストコース', category='テスト研修',
                   training_type='eラーニング', total_hours=1.0, pass_score=80,
                   is_published=True)
        db.session.add(c)
        db.session.flush()
        lessons = []
        for i in range(1, 4):
            l = Lesson(course_id=c.id, title=f'レッスン{i}', content=f'本文{i}',
                       video_url='https://youtu.be/dummy', duration_seconds=600,
                       duration_minutes=10, order=i)
            db.session.add(l)
            lessons.append(l)
        u = User(username='emp', email='emp@example.com',
                 password_hash=generate_password_hash('pass1234'),
                 role='employee', full_name='検証太郎', employee_id='E999')
        db.session.add(u)
        db.session.flush()
        db.session.add(Enrollment(user_id=u.id, course_id=c.id))
        db.session.commit()
        return {'course_id': c.id, 'user_id': u.id,
                'lesson_ids': [l.id for l in lessons]}


def login(client, username='emp', password='pass1234'):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)
