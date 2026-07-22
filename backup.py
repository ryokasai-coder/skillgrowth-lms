"""
受講データ5年保存バックアップスクリプト
- SQLiteファイルのタイムスタンプ付きコピーを作成
- 全受講ログをCSVでエクスポート
- 5年を超えた古いバックアップを自動削除

実行方法:
  python backup.py

Windowsタスクスケジューラへの登録例（毎日AM2時）:
  タスク名: LMS_Backup
  プログラム: python.exe
  引数: C:\\Users\\ryo19\\lms-project\\backup.py
  開始時刻: 02:00
"""
import os
import shutil
import sqlite3
import csv
from datetime import datetime, timedelta

BASE_DIR    = os.path.dirname(__file__)
DB_PATH     = os.path.join(BASE_DIR, 'instance', 'lms.db')
BACKUP_DIR  = os.path.join(BASE_DIR, 'backups')
RETAIN_DAYS = 365 * 5  # 5年

def run_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 1. DBファイルのコピー
    if os.path.exists(DB_PATH):
        dest = os.path.join(BACKUP_DIR, f'lms_{ts}.db')
        shutil.copy2(DB_PATH, dest)
        print(f'DBバックアップ: {dest}')
    else:
        print(f'警告: DBファイルが見つかりません ({DB_PATH})')
        return

    # 2. 全受講ログをCSVエクスポート
    csv_path = os.path.join(BACKUP_DIR, f'logs_{ts}.csv')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''
            SELECT
                sl.id, u.employee_id, u.full_name, u.department, u.employment_type,
                co.title, co.training_type, l.title,
                sl.login_at, sl.logout_at, sl.duration_seconds,
                ROUND(sl.duration_seconds / 3600.0, 4),
                sl.ip_address
            FROM study_log sl
            JOIN user u ON sl.user_id = u.id
            JOIN course co ON sl.course_id = co.id
            LEFT JOIN lesson l ON sl.lesson_id = l.id
            ORDER BY sl.login_at ASC
        ''')
        rows = c.fetchall()
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ログID', '社員番号', '氏名', '部署', '雇用形態',
                'コース名', '訓練種別', 'レッスン名',
                '視聴開始日時', '視聴終了日時', '視聴時間（秒）', '視聴時間（時間）',
                'IPアドレス'
            ])
            writer.writerows(rows)
        print(f'ログCSV出力: {csv_path} ({len(rows)}件)')
    except Exception as e:
        print(f'CSV出力エラー: {e}')
    finally:
        conn.close()

    # 3. 保持期限切れバックアップを削除
    cutoff = datetime.now() - timedelta(days=RETAIN_DAYS)
    removed = 0
    for fname in os.listdir(BACKUP_DIR):
        fpath = os.path.join(BACKUP_DIR, fname)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime < cutoff:
            os.remove(fpath)
            removed += 1
    if removed:
        print(f'期限切れバックアップ削除: {removed}件')

    print('バックアップ完了')

if __name__ == '__main__':
    run_backup()
