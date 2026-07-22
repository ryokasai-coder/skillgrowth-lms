from app import app, db, User, Course, Lesson, Quiz, Question, Enrollment
from werkzeug.security import generate_password_hash
from datetime import date

with app.app_context():
    # サンプル受講者
    if not User.query.filter_by(username='tanaka').first():
        users = [
            User(username='tanaka', email='tanaka@example.com',
                 password_hash=generate_password_hash('pass123'),
                 full_name='田中 太郎', employee_id='E001', department='営業部',
                 employment_type='正社員', hire_date=date(2020, 4, 1), role='employee'),
            User(username='sato', email='sato@example.com',
                 password_hash=generate_password_hash('pass123'),
                 full_name='佐藤 花子', employee_id='E002', department='総務部',
                 employment_type='正社員', hire_date=date(2019, 7, 1), role='employee'),
        ]
        for u in users:
            db.session.add(u)
        db.session.commit()

    # サンプルコース
    if not Course.query.first():
        admin = User.query.filter_by(username='admin').first()
        course = Course(
            title='情報セキュリティ基礎訓練',
            description='企業の情報セキュリティに関する基礎知識を習得します。個人情報保護、サイバー攻撃への対策、セキュリティポリシーの理解を深めます。',
            training_type='一般訓練コース',
            category='IT・デジタル',
            total_hours=10.0,
            pass_score=70,
            is_published=True,
            created_by=admin.id
        )
        db.session.add(course)
        db.session.commit()

        lessons = [
            Lesson(course_id=course.id, title='情報セキュリティとは', order=1, duration_minutes=60,
                   content='情報セキュリティとは、情報資産を保護するための概念です。\n\n■ 情報の3要素\n・機密性（Confidentiality）: 許可された者だけが情報にアクセスできること\n・完全性（Integrity）: 情報が正確・完全であること\n・可用性（Availability）: 必要な時に情報が使えること\n\n■ 主な脅威\n・マルウェア（ウイルス・ランサムウェア等）\n・フィッシング詐欺\n・標的型攻撃\n・内部不正\n\n■ 基本的な対策\n・OSやソフトウェアを常に最新版に更新する\n・強固なパスワードを設定し、定期的に変更する\n・不審なメールの添付ファイルやURLを開かない'),
            Lesson(course_id=course.id, title='パスワード管理と認証', order=2, duration_minutes=60,
                   content='安全なパスワード管理と多要素認証について学びます。\n\n■ 強いパスワードの条件\n・8文字以上（推奨：12文字以上）\n・英大文字・小文字・数字・記号を組み合わせる\n・推測されやすい言葉（誕生日・名前等）を使わない\n・サービスごとに異なるパスワードを使用する\n\n■ パスワードマネージャーの活用\n複数のパスワードを安全に管理するためにパスワードマネージャーの利用を推奨します。\n\n■ 多要素認証（MFA）\nパスワードに加えて、スマートフォンのアプリやSMSによる認証を追加することで、セキュリティを大幅に向上できます。'),
            Lesson(course_id=course.id, title='個人情報保護法と対応', order=3, duration_minutes=90,
                   content='個人情報保護法の概要と企業としての対応を学びます。\n\n■ 個人情報とは\n生存する個人に関する情報で、氏名・生年月日等により特定の個人を識別できるもの\n\n■ 個人情報取扱事業者の義務\n・利用目的の特定・公表\n・安全管理措置の実施\n・第三者提供の制限\n・保有個人データの開示・訂正・削除への対応\n\n■ 違反した場合のリスク\n・行政処分（勧告・命令）\n・刑事罰（1年以下の懲役または100万円以下の罰金）\n・企業への信頼失墜'),
            Lesson(course_id=course.id, title='インシデント対応手順', order=4, duration_minutes=60,
                   content='情報セキュリティインシデント発生時の対応手順を学びます。\n\n■ インシデントの種類\n・マルウェア感染\n・不正アクセス\n・情報漏えい\n・システム障害\n\n■ 対応の基本手順\n1. 検知・報告: 上長および情報システム部門に即時報告\n2. 初動対応: 感染端末のネットワーク切断\n3. 調査・分析: 被害範囲の特定\n4. 封じ込め・復旧: システムの復旧\n5. 事後対応: 原因分析と再発防止策の策定\n\n■ 重要なポイント\n一人で対応しようとせず、必ず組織内で情報共有することが重要です。'),
        ]
        for l in lessons:
            db.session.add(l)
        db.session.commit()

        quiz = Quiz(course_id=course.id, title='情報セキュリティ基礎 理解度テスト')
        db.session.add(quiz)
        db.session.commit()

        questions = [
            Question(quiz_id=quiz.id, question_text='情報セキュリティの3要素として正しいものはどれですか？', order=1,
                     option_a='機密性・完全性・可用性', option_b='機密性・信頼性・効率性',
                     option_c='安全性・完全性・利便性', option_d='機密性・信頼性・可用性',
                     correct_answer='A'),
            Question(quiz_id=quiz.id, question_text='強いパスワードの条件として適切でないものはどれですか？', order=2,
                     option_a='8文字以上にする', option_b='誕生日をそのまま使用する',
                     option_c='英大文字・小文字・数字・記号を組み合わせる', option_d='サービスごとに異なるパスワードを使用する',
                     correct_answer='B'),
            Question(quiz_id=quiz.id, question_text='情報セキュリティインシデント発生時の初動対応として最初にすべきことは？', order=3,
                     option_a='一人で解決しようとする', option_b='パスワードを変更する',
                     option_c='上長および情報システム部門に即時報告する', option_d='PCを再起動する',
                     correct_answer='C'),
            Question(quiz_id=quiz.id, question_text='個人情報保護法における「個人情報」の説明として正しいものはどれですか？', order=4,
                     option_a='企業の財務情報', option_b='生存する個人に関する情報で特定の個人を識別できるもの',
                     option_c='すべての電子データ', option_d='社外秘扱いの情報全般',
                     correct_answer='B'),
            Question(quiz_id=quiz.id, question_text='多要素認証（MFA）の目的として正しいものはどれですか？', order=5,
                     option_a='パスワードを不要にする', option_b='ログインを簡単にする',
                     option_c='パスワードに加えて別の認証要素を追加しセキュリティを強化する', option_d='個人情報を保護する',
                     correct_answer='C'),
        ]
        for q in questions:
            db.session.add(q)
        db.session.commit()
        print('サンプルデータを投入しました')
        print('受講者アカウント: tanaka / pass123, sato / pass123')
    else:
        print('データはすでに存在します')
