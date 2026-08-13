"""既存の視聴秒数を動画全長でキャップし、コース累計(total_study_seconds)を再計算する補正スクリプト。

背景: ハートビート積算に動画長の上限が無かったため、一時停止・タブ切替からの再開時の
加算誤差で「1レッスンの視聴時間」が動画全長を超えて記録されるケースがあった（app.py側で修正済み）。
本スクリプトは既存データを是正する。冪等（何度実行しても結果は同じ）。

実行:  python fix_watch_seconds.py
"""
from app import app, db, LessonProgress, StudyLog, Enrollment, Lesson

with app.app_context():
    fixed_lp = fixed_log = 0

    # 1) レッスン進捗の実視聴秒数を動画長でキャップ
    for lp in LessonProgress.query.all():
        lesson = Lesson.query.get(lp.lesson_id)
        cap = (lesson.duration_seconds or 0) if lesson else 0
        if cap and (lp.actual_watch_seconds or 0) > cap:
            lp.actual_watch_seconds = cap
            fixed_lp += 1

    # 2) 受講ログ(StudyLog)の視聴秒数を動画長でキャップ
    for log in StudyLog.query.all():
        lesson = Lesson.query.get(log.lesson_id) if log.lesson_id else None
        cap = (lesson.duration_seconds or 0) if lesson else 0
        if cap and (log.duration_seconds or 0) > cap:
            log.duration_seconds = cap
            fixed_log += 1

    # 3) コース累計(total_study_seconds)を各レッスンの実視聴秒数の合計で再計算
    for e in Enrollment.query.all():
        e.total_study_seconds = sum((lp.actual_watch_seconds or 0) for lp in e.lesson_progress)

    db.session.commit()
    print(f'done: lesson_progress {fixed_lp}件 / study_log {fixed_log}件 をキャップ、'
          f'enrollment累計を再計算しました')
