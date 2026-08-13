"""テスト受講記録を初期化する（本番稼働前のテストデータ一掃用）。

受講ログ(StudyLog)・ログイン証跡(LoginSession)・テスト解答(QuizAttempt)・視聴進捗(LessonProgress)を
削除し、Enrollmentの集計値（実視聴時間・進捗率・点数・状態・開始/修了日時）をリセットする。
ユーザーアカウント・コース・動画などの教材は残す。冪等（再実行しても安全）。

実行前に必ずDBバックアップを取ること。実行手順（本番）:
  cp ~/lms-project/instance/lms.db ~/lms-project/instance/lms_backup_before_reset.db
  LMS_DATABASE_URI="sqlite:////home/skillgrowth/lms-project/instance/lms.db" \
    ~/.virtualenvs/lms-venv/bin/python reset_test_records.py
"""
from app import app, db, StudyLog, LoginSession, QuizAttempt, LessonProgress, Enrollment

with app.app_context():
    print('--- 削除前の件数 ---')
    print('StudyLog       :', StudyLog.query.count())
    print('LoginSession   :', LoginSession.query.count())
    print('QuizAttempt    :', QuizAttempt.query.count())
    print('LessonProgress :', LessonProgress.query.count())
    print('Enrollment     :', Enrollment.query.count(), '（削除せず集計値のみリセット）')

    StudyLog.query.delete()
    LoginSession.query.delete()
    QuizAttempt.query.delete()
    LessonProgress.query.delete()
    for e in Enrollment.query.all():
        e.started_at = None
        e.completed_at = None
        e.total_study_seconds = 0
        e.quiz_score = None
        e.quiz_attempts = 0
        e.progress_percent = 0
        e.status = 'enrolled'
    db.session.commit()

    print('--- 削除後の件数 ---')
    print('StudyLog       :', StudyLog.query.count())
    print('LoginSession   :', LoginSession.query.count())
    print('QuizAttempt    :', QuizAttempt.query.count())
    print('LessonProgress :', LessonProgress.query.count())
    print('完了: Enrollmentの集計値をリセットしました（登録自体は保持）')
