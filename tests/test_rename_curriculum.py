"""rename_curriculum: コースのカテゴリと会社の受講可能設定を同時に改名する。"""
from app import app, db, Course, Company, CompanyCurriculum
from rename_curriculum import rename


def _setup():
    with app.app_context():
        _seed()


def _count(model, **kw):
    with app.app_context():
        return model.query.filter_by(**kw).count()


def _seed():
    co = Company(name='テスト社')
    db.session.add(co)
    db.session.add_all([Course(title='第1章', category='旧名'), Course(title='第2章', category='旧名'),
                        Course(title='別', category='別講座')])
    db.session.flush()
    db.session.add(CompanyCurriculum(company_id=co.id, curriculum_name='旧名'))
    db.session.commit()


def test_dry_run_changes_nothing():
    _setup()
    assert rename('旧名', '新名', commit=False)
    assert _count(Course, category='旧名') == 2
    assert _count(CompanyCurriculum, curriculum_name='旧名') == 1


def test_commit_renames_both_tables():
    _setup()
    assert rename('旧名', '新名', commit=True)
    assert _count(Course, category='新名') == 2
    assert _count(Course, category='別講座') == 1
    assert _count(CompanyCurriculum, curriculum_name='新名') == 1


def test_refuses_existing_name():
    _setup()
    assert not rename('旧名', '別講座', commit=True)
    assert _count(Course, category='旧名') == 2
