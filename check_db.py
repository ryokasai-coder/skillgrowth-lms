import sqlite3
db = 'C:/Users/ryo19/lms-project/instance/lms.db'
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in c.fetchall()]
print('テーブル一覧:', tables)

# 新カラム確認
checks = [
    ('user', 'force_password_change'),
    ('enrollment', 'total_study_seconds'),
    ('lesson_progress', 'actual_watch_seconds'),
    ('lesson_progress', 'last_position_seconds'),
    ('study_log', 'duration_seconds'),
]
for table, col in checks:
    c.execute(f'PRAGMA table_info({table})')
    cols = [r[1] for r in c.fetchall()]
    ok = col in cols
    print(f'  {"OK" if ok else "NG"}: {table}.{col}')
conn.close()
