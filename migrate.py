"""
データベースマイグレーションスクリプト
既存のlms.dbに新しいカラムを追加します（データは保持されます）
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'lms.db')

def column_exists(cursor, table, column):
    cursor.execute(f'PRAGMA table_info({table})')
    return any(row[1] == column for row in cursor.fetchall())

def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None

def migrate():
    if not os.path.exists(DB_PATH):
        print(f'DBファイルが見つかりません: {DB_PATH}')
        print('app.pyを起動してDBを初期化してください')
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    migrations = []

    # user: force_password_change
    if not column_exists(c, 'user', 'force_password_change'):
        c.execute('ALTER TABLE user ADD COLUMN force_password_change BOOLEAN DEFAULT 0')
        migrations.append('user.force_password_change')

    # user: ログイン試行制限
    if not column_exists(c, 'user', 'failed_login_count'):
        c.execute('ALTER TABLE user ADD COLUMN failed_login_count INTEGER DEFAULT 0')
        migrations.append('user.failed_login_count')
    if not column_exists(c, 'user', 'lockout_until'):
        c.execute('ALTER TABLE user ADD COLUMN lockout_until DATETIME')
        migrations.append('user.lockout_until')

    # user: MFA（TOTP）
    if not column_exists(c, 'user', 'mfa_secret'):
        c.execute('ALTER TABLE user ADD COLUMN mfa_secret VARCHAR(32)')
        migrations.append('user.mfa_secret')
    if not column_exists(c, 'user', 'mfa_enabled'):
        c.execute('ALTER TABLE user ADD COLUMN mfa_enabled BOOLEAN DEFAULT 0')
        migrations.append('user.mfa_enabled')

    # course: sort_order（カリキュラム内の表示順）
    if not column_exists(c, 'course', 'sort_order'):
        c.execute('ALTER TABLE course ADD COLUMN sort_order INTEGER DEFAULT 0')
        migrations.append('course.sort_order')

    # enrollment: progress_percent（進捗率）
    if not column_exists(c, 'enrollment', 'progress_percent'):
        c.execute('ALTER TABLE enrollment ADD COLUMN progress_percent INTEGER DEFAULT 0')
        migrations.append('enrollment.progress_percent')

    # enrollment: total_study_seconds（旧: total_study_minutes * 60 で移行）
    if not column_exists(c, 'enrollment', 'total_study_seconds'):
        c.execute('ALTER TABLE enrollment ADD COLUMN total_study_seconds INTEGER DEFAULT 0')
        # 既存データをマイグレーション（分 → 秒）
        if column_exists(c, 'enrollment', 'total_study_minutes'):
            c.execute('UPDATE enrollment SET total_study_seconds = total_study_minutes * 60')
        migrations.append('enrollment.total_study_seconds')

    # lesson_progress: actual_watch_seconds
    if not column_exists(c, 'lesson_progress', 'actual_watch_seconds'):
        c.execute('ALTER TABLE lesson_progress ADD COLUMN actual_watch_seconds INTEGER DEFAULT 0')
        # 既存データから推定（study_minutesがあれば秒に変換）
        if column_exists(c, 'lesson_progress', 'study_minutes'):
            c.execute('UPDATE lesson_progress SET actual_watch_seconds = study_minutes * 60')
        migrations.append('lesson_progress.actual_watch_seconds')

    # lesson_progress: last_position_seconds
    if not column_exists(c, 'lesson_progress', 'last_position_seconds'):
        c.execute('ALTER TABLE lesson_progress ADD COLUMN last_position_seconds INTEGER DEFAULT 0')
        migrations.append('lesson_progress.last_position_seconds')

    # lesson_progress: last_heartbeat_at（改ざん防止: サーバ実時間ベースの加算制限用）
    if not column_exists(c, 'lesson_progress', 'last_heartbeat_at'):
        c.execute('ALTER TABLE lesson_progress ADD COLUMN last_heartbeat_at DATETIME')
        migrations.append('lesson_progress.last_heartbeat_at')

    # study_log: duration_seconds（旧: duration_minutes * 60 で移行）
    if not column_exists(c, 'study_log', 'duration_seconds'):
        c.execute('ALTER TABLE study_log ADD COLUMN duration_seconds INTEGER DEFAULT 0')
        if column_exists(c, 'study_log', 'duration_minutes'):
            c.execute('UPDATE study_log SET duration_seconds = duration_minutes * 60')
        migrations.append('study_log.duration_seconds')

    # active_session テーブル作成
    if not table_exists(c, 'active_session'):
        c.execute('''CREATE TABLE active_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE REFERENCES user(id),
            token VARCHAR(100) NOT NULL,
            logged_in_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        migrations.append('テーブル: active_session')

    # login_session テーブル作成（ログイン/ログアウト証跡）
    if not table_exists(c, 'login_session'):
        c.execute('''CREATE TABLE login_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES user(id),
            login_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            logout_at DATETIME,
            logout_reason VARCHAR(30),
            ip_address VARCHAR(50)
        )''')
        migrations.append('テーブル: login_session')

    # quiz_attempt テーブル作成
    if not table_exists(c, 'quiz_attempt'):
        c.execute('''CREATE TABLE quiz_attempt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES user(id),
            course_id INTEGER NOT NULL REFERENCES course(id),
            quiz_id INTEGER NOT NULL REFERENCES quiz(id),
            attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            score INTEGER,
            answers_json TEXT,
            ip_address VARCHAR(50)
        )''')
        migrations.append('テーブル: quiz_attempt')

    conn.commit()
    conn.close()

    if migrations:
        print('マイグレーション完了:')
        for m in migrations:
            print(f'  + {m}')
    else:
        print('マイグレーション不要（すべて最新）')

if __name__ == '__main__':
    migrate()
