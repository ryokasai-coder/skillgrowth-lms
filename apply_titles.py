"""タイトル決めシート(CSV書き出し)をLMSに反映する。

    LMS_DATABASE_URI=... python apply_titles.py titles.csv --copy "デジタルマーケティング研修" --rename "AIリスキリング研修"
    （--commit を付けるまではドライラン）

CSV列: カリキュラム（現在）,章No,章タイトル（現在）,動画No,動画タイトル（現在）,長さ(分),新カリキュラム名,新 章タイトル,新 動画タイトル,メモ
- 章No/動画No は カリキュラム内の (Course.sort_order, id) / (Lesson.order, id) 順の通し番号。
- 「現在」列がDBと1件でも食い違えば何もせず中止する（シート作成後にDBが変わった場合の事故防止）。
- --copy: 元は残し、同じ動画URL・動画長で新カリキュラムとして複製する（受講記録は引き継がない）。
- --rename: そのカリキュラムを新名に改名し（会社の受講可能設定も追随）、記入のある章/動画タイトルだけ変える。
- 新タイトルが空欄の章/動画は現在のタイトルのまま。
"""
import csv
import sys

from app import app, db, Course, Lesson, CompanyCurriculum


def _load(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    plan = {}
    for r in rows:
        cat = r['カリキュラム（現在）'].strip()
        p = plan.setdefault(cat, {'new_name': '', 'chapters': {}})
        if r.get('新カリキュラム名', '').strip() and not p['new_name']:
            p['new_name'] = r['新カリキュラム名'].strip()
        ch = p['chapters'].setdefault(int(r['章No']), {'cur': '', 'new': '', 'videos': {}})
        if r['章タイトル（現在）'].strip():
            ch['cur'] = r['章タイトル（現在）'].strip()
        if r.get('新 章タイトル', '').strip():
            ch['new'] = r['新 章タイトル'].strip()
        ch['videos'][int(r['動画No'])] = {'cur': r['動画タイトル（現在）'].strip(),
                                          'new': r.get('新 動画タイトル', '').strip()}
    return plan


def _db_structure(cat):
    courses = Course.query.filter_by(category=cat).order_by(Course.sort_order, Course.id).all()
    return [(c, Lesson.query.filter_by(course_id=c.id).order_by(Lesson.order, Lesson.id).all())
            for c in courses]


def _check(cat, p, struct):
    errs = []
    if len(struct) != len(p['chapters']):
        errs.append(f'{cat}: 章の数が違います (DB {len(struct)} / シート {len(p["chapters"])})')
        return errs
    for i, (c, lessons) in enumerate(struct, 1):
        ch = p['chapters'][i]
        if ch['cur'] != c.title.strip():
            errs.append(f'{cat} 章{i}: 「{ch["cur"]}」≠DB「{c.title}」')
        if len(lessons) != len(ch['videos']):
            errs.append(f'{cat} 章{i}: 動画数が違います (DB {len(lessons)} / シート {len(ch["videos"])})')
            continue
        for j, l in enumerate(lessons, 1):
            if ch['videos'][j]['cur'] != l.title.strip():
                errs.append(f'{cat} 章{i} 動画{j}: 「{ch["videos"][j]["cur"]}」≠DB「{l.title}」')
    return errs


def apply(path, copy_cats=(), rename_cats=(), commit=False):
    plan = _load(path)
    with app.app_context():
        errs, todo = [], []
        for cat, mode in [(c, 'copy') for c in copy_cats] + [(c, 'rename') for c in rename_cats]:
            if cat not in plan:
                errs.append(f'シートに「{cat}」がありません')
                continue
            p = plan[cat]
            if not p['new_name']:
                errs.append(f'{cat}: 新カリキュラム名が空です')
                continue
            if Course.query.filter_by(category=p['new_name']).count():
                errs.append(f'{cat}: 新名「{p["new_name"]}」はすでに使われています')
                continue
            struct = _db_structure(cat)
            errs += _check(cat, p, struct)
            todo.append((cat, mode, p, struct))
        if errs:
            print('中止しました（DBは変更していません）:')
            for e in errs:
                print('  -', e)
            return False

        for cat, mode, p, struct in todo:
            changed = 0
            for i, (c, lessons) in enumerate(struct, 1):
                ch = p['chapters'][i]
                if mode == 'copy':
                    nc = Course(title=ch['new'] or c.title, description=c.description,
                                training_type=c.training_type, category=p['new_name'],
                                total_hours=c.total_hours, pass_score=c.pass_score,
                                sort_order=c.sort_order, is_published=c.is_published,
                                created_by=c.created_by)
                    db.session.add(nc)
                    db.session.flush()
                    for j, l in enumerate(lessons, 1):
                        db.session.add(Lesson(course_id=nc.id, title=ch['videos'][j]['new'] or l.title,
                                              content=l.content, video_url=l.video_url,
                                              duration_minutes=l.duration_minutes,
                                              duration_seconds=l.duration_seconds, order=l.order))
                        changed += 1
                else:
                    c.category = p['new_name']
                    if ch['new']:
                        c.title = ch['new']
                    for j, l in enumerate(lessons, 1):
                        if ch['videos'][j]['new']:
                            l.title = ch['videos'][j]['new']
                            changed += 1
            if mode == 'rename':
                for link in CompanyCurriculum.query.filter_by(curriculum_name=cat).all():
                    link.curriculum_name = p['new_name']
            label = '複製' if mode == 'copy' else '改名'
            what = '動画複製' if mode == 'copy' else '動画タイトル変更'
            print(f'{label}: 「{cat}」→「{p["new_name"]}」 章{len(struct)} / {what}{changed}件')
        if commit:
            db.session.commit()
            print('反映しました')
        else:
            db.session.rollback()
            print('ドライランです（--commit で反映）')
        return True


if __name__ == '__main__':
    a = sys.argv[1:]
    copies, renames, path = [], [], None
    i = 0
    while i < len(a):
        if a[i] == '--copy':
            copies.append(a[i + 1])
            i += 2
        elif a[i] == '--rename':
            renames.append(a[i + 1])
            i += 2
        elif a[i] == '--commit':
            i += 1
        else:
            path = a[i]
            i += 1
    if not path or not (copies or renames):
        print(__doc__)
        sys.exit(1)
    sys.exit(0 if apply(path, copies, renames, '--commit' in a) else 1)
