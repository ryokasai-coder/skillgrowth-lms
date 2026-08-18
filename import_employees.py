"""受講者アカウントと受講登録をCSVから一括投入する（冪等・再実行安全）。

CSV（UTF-8, ヘッダ付き。Excel保存のBOMも許容）の列:
    username        ログインID（必須・ユニーク。既存ならプロフィール更新のみ）
    email           メール（必須・ユニーク）
    password        初期パスワード（新規作成時のみ使用。既存ユーザーには影響しない）
    full_name       氏名（必須）
    employee_id     社員番号（任意・助成金の証憑用）
    department      部署（任意・証憑用）
    employment_type 雇用形態（任意・証憑用。例: 正社員/パート）
    hire_date       入社日（任意・YYYY-MM-DD）
    company         所属会社名（任意。無ければ未所属。get-or-createで会社も作成）
    curriculum      受講させるカリキュラム名（任意。Course.category と一致。
                    そのカテゴリの公開コースへ一括受講登録。既存はスキップ）

使い方（本番）:
    LMS_DATABASE_URI="sqlite:////home/skillgrowth/lms-project/instance/lms.db" \
    ~/.virtualenvs/lms-venv/bin/python ~/lms-project/import_employees.py employees.csv
    末尾に --commit を付けると実際に書き込む。付けないとドライラン（何もDBに書かない）。
"""
import csv
import sys
from datetime import datetime

from app import app, db, Company, User, Course, Enrollment
from werkzeug.security import generate_password_hash


def _get_or_create_company(name):
    name = (name or '').strip()
    if not name:
        return None, False
    c = Company.query.filter_by(name=name).first()
    if c:
        return c, False
    c = Company(name=name)
    db.session.add(c)
    db.session.flush()
    return c, True


def _parse_date(s):
    s = (s or '').strip()
    if not s:
        return None
    return datetime.strptime(s, '%Y-%m-%d').date()


def run(csv_path, commit):
    stats = {'companies_new': 0, 'users_new': 0, 'users_updated': 0,
             'enrollments_new': 0, 'rows': 0, 'errors': []}
    with app.app_context():
        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=2):  # 2 = ヘッダの次の行
                row = {(k or '').strip(): (v or '').strip() for k, v in row.items()}
                username = row.get('username', '')
                if not username:
                    continue  # 空行スキップ
                stats['rows'] += 1
                try:
                    if not row.get('email') or not row.get('full_name'):
                        raise ValueError('email と full_name は必須')

                    company, made = _get_or_create_company(row.get('company'))
                    if made:
                        stats['companies_new'] += 1

                    user = User.query.filter_by(username=username).first()
                    if user is None:
                        if not row.get('password'):
                            raise ValueError('新規ユーザーには password が必須')
                        user = User(
                            username=username,
                            email=row['email'],
                            password_hash=generate_password_hash(row['password']),
                            full_name=row['full_name'],
                            employee_id=row.get('employee_id', ''),
                            department=row.get('department', ''),
                            employment_type=row.get('employment_type', ''),
                            hire_date=_parse_date(row.get('hire_date')),
                            role='employee',
                            company_id=company.id if company else None,
                            force_password_change=True,  # 初回ログインでPW変更を強制
                        )
                        db.session.add(user)
                        db.session.flush()
                        stats['users_new'] += 1
                    else:
                        # 既存ユーザーはプロフィールのみ更新（パスワードは触らない）
                        user.email = row['email']
                        user.full_name = row['full_name']
                        user.employee_id = row.get('employee_id', '') or user.employee_id
                        user.department = row.get('department', '') or user.department
                        user.employment_type = row.get('employment_type', '') or user.employment_type
                        hd = _parse_date(row.get('hire_date'))
                        if hd:
                            user.hire_date = hd
                        if company:
                            user.company_id = company.id
                        stats['users_updated'] += 1

                    curriculum = row.get('curriculum', '')
                    if curriculum:
                        courses = Course.query.filter_by(category=curriculum,
                                                         is_published=True).all()
                        if not courses:
                            raise ValueError(f'カリキュラム「{curriculum}」に公開コースが無い')
                        for course in courses:
                            exists = Enrollment.query.filter_by(
                                user_id=user.id, course_id=course.id).first()
                            if not exists:
                                db.session.add(Enrollment(user_id=user.id,
                                                          course_id=course.id))
                                stats['enrollments_new'] += 1
                except Exception as e:  # noqa: BLE001
                    stats['errors'].append(f'行{i}({username}): {e}')

        if commit and not stats['errors']:
            db.session.commit()
            mode = 'COMMITTED'
        else:
            db.session.rollback()
            mode = 'DRY-RUN (rolled back)' if not commit else 'ERRORS -> rolled back'

    print('=== import_employees:', mode, '===')
    for k in ['rows', 'companies_new', 'users_new', 'users_updated', 'enrollments_new']:
        print(f'{k}: {stats[k]}')
    if stats['errors']:
        print('--- errors ---')
        for e in stats['errors']:
            print(e)
    print('（--commit 無し=ドライラン。エラーがあると commit してもロールバックします）'
          if not commit or stats['errors'] else '（DBに反映しました）')
    return 1 if stats['errors'] else 0


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    commit = '--commit' in sys.argv
    if not args:
        print('使い方: python import_employees.py <csvパス> [--commit]')
        sys.exit(2)
    sys.exit(run(args[0], commit))
