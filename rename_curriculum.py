"""カリキュラム名（Course.category と CompanyCurriculum.curriculum_name）を一括で変更する。

    LMS_DATABASE_URI=... python rename_curriculum.py "旧名" "新名"           # ドライラン
    LMS_DATABASE_URI=... python rename_curriculum.py "旧名" "新名" --commit  # 反映

修了証のカリキュラム名・受講登録の絞り込みはこの名前で行うため、両テーブルを同時に変える。
"""
import sys

from app import app, db, Course, CompanyCurriculum


def rename(old, new, commit=False):
    with app.app_context():
        courses = Course.query.filter_by(category=old).all()
        links = CompanyCurriculum.query.filter_by(curriculum_name=old).all()
        clash = Course.query.filter_by(category=new).count()
        print(f'コース {len(courses)} 件 / 会社の受講可能設定 {len(links)} 件: 「{old}」→「{new}」')
        if clash:
            print(f'中止: 「{new}」はすでに {clash} 件のコースで使われています')
            return False
        if not courses and not links:
            print('対象がありません')
            return False
        for c in courses:
            c.category = new
        for l in links:
            l.curriculum_name = new
        if commit:
            db.session.commit()
            print('反映しました')
        else:
            db.session.rollback()
            print('ドライランです（--commit で反映）')
        return True


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--commit']
    if len(args) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(0 if rename(args[0], args[1], '--commit' in sys.argv) else 1)
