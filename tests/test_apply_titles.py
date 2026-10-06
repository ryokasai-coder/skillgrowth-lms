"""apply_titles: シートの新タイトルで複製/改名する。現在タイトルの食い違いでは中止する。"""
import csv

from app import app, db, Course, Lesson, Company, CompanyCurriculum
from apply_titles import apply

HEAD = ['カリキュラム（現在）', '章No', '章タイトル（現在）', '動画No', '動画タイトル（現在）', '長さ(分)',
        '新カリキュラム名', '新 章タイトル', '新 動画タイトル', 'メモ']

ROWS = [
    ['DM', 1, 'DM章1', 1, 'DM1-1', 1, 'DM店舗', '新章1', '新動画11', ''],
    ['DM', 1, '', 2, 'DM1-2', 2, '', '', '', ''],
    ['DM', 2, 'DM章2', 1, 'DM2-1', 1, '', '', '新動画21', ''],
    ['DM', 2, '', 2, 'DM2-2', 2, '', '', '', ''],
    ['AI', 1, 'AI章1', 1, 'AI1-1', 1, 'AI店舗', '', '新AI11', ''],
    ['AI', 1, '', 2, 'AI1-2', 2, '', '', '', ''],
]


def _seed():
    with app.app_context():
        for cat, n in [('DM', 2), ('AI', 1)]:
            for ci in range(1, n + 1):
                c = Course(title=f'{cat}章{ci}', category=cat, sort_order=ci, is_published=True)
                db.session.add(c)
                db.session.flush()
                for li in range(1, 3):
                    db.session.add(Lesson(course_id=c.id, title=f'{cat}{ci}-{li}', order=li,
                                          video_url=f'https://youtu.be/{cat}{ci}{li}',
                                          duration_seconds=60 * li))
        co = Company(name='社')
        db.session.add(co)
        db.session.flush()
        db.session.add(CompanyCurriculum(company_id=co.id, curriculum_name='AI'))
        db.session.commit()


def _csv(tmp_path, rows):
    p = tmp_path / 't.csv'
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerows(rows)
    return str(p)


def _q(fn):
    with app.app_context():
        return fn()


def test_copy_and_rename(tmp_path):
    _seed()
    assert apply(_csv(tmp_path, ROWS), ['DM'], ['AI'], commit=True)
    assert _q(lambda: Course.query.filter_by(category='DM').count()) == 2
    assert _q(lambda: [c.title for c in Course.query.filter_by(category='DM店舗')
                       .order_by(Course.sort_order)]) == ['新章1', 'DM章2']
    assert _q(lambda: Lesson.query.filter_by(title='新動画11').first().video_url) == 'https://youtu.be/DM11'
    assert _q(lambda: Lesson.query.filter_by(title='DM1-1').count()) == 1   # 元は残る
    assert _q(lambda: Lesson.query.filter_by(title='DM1-2').count()) == 2   # 空欄は現タイトルで複製
    assert _q(lambda: Course.query.filter_by(category='AI').count()) == 0
    assert _q(lambda: Lesson.query.filter_by(title='新AI11').count()) == 1
    assert _q(lambda: CompanyCurriculum.query.first().curriculum_name) == 'AI店舗'


def test_dry_run_changes_nothing(tmp_path):
    _seed()
    assert apply(_csv(tmp_path, ROWS), ['DM'], ['AI'], commit=False)
    assert _q(lambda: Course.query.filter_by(category='DM店舗').count()) == 0
    assert _q(lambda: Course.query.filter_by(category='AI').count()) == 1


def test_mismatch_aborts(tmp_path):
    _seed()
    bad = [r[:] for r in ROWS]
    bad[1][4] = '違うタイトル'
    assert not apply(_csv(tmp_path, bad), ['DM'], ['AI'], commit=True)
    assert _q(lambda: Course.query.filter_by(category='DM店舗').count()) == 0
    assert _q(lambda: Course.query.filter_by(category='AI').count()) == 1
