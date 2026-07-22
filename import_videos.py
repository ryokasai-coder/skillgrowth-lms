"""
CSVの動画リストをLMSにインポートするスクリプト
各章を1コースとして作成し、動画をレッスンとして登録する
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, Course, Lesson

CSV_PATH = r"C:\Users\ryo19\Downloads\動画リンク - 動画リンク.csv"

def parse_csv(path):
    chapters = []
    current_chapter = None
    pending_title = None

    with open(path, encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.rstrip("\n").strip()
            if not line:
                pending_title = None
                continue

            # 章タイトル行（「第X章」で始まる）
            if line.startswith("第") and "章" in line:
                current_chapter = {"title": line, "lessons": []}
                chapters.append(current_chapter)
                pending_title = None
                continue

            # URLかどうか判定
            if line.startswith("http"):
                if current_chapter is not None and pending_title:
                    current_chapter["lessons"].append({
                        "title": pending_title,
                        "url": line,
                    })
                pending_title = None
            else:
                # 次の行がURLのはずのレッスンタイトル
                pending_title = line

    return chapters


def import_data(chapters):
    with app.app_context():
        total_courses = 0
        total_lessons = 0

        for ch in chapters:
            # 既存コースがあればスキップ
            existing = Course.query.filter_by(title=ch["title"]).first()
            if existing:
                print(f"  スキップ（既存）: {ch['title']}")
                continue

            course = Course(
                title=ch["title"],
                description=ch["title"],
                training_type="eラーニング",
                category="SNS運用",
                total_hours=round(len(ch["lessons"]) * 10 / 60, 1),
                pass_score=80,
                is_published=True,
                created_by=1,  # admin
            )
            db.session.add(course)
            db.session.flush()  # IDを確定

            for order, lesson in enumerate(ch["lessons"], start=1):
                db.session.add(Lesson(
                    course_id=course.id,
                    title=lesson["title"],
                    video_url=lesson["url"],
                    order=order,
                    duration_minutes=10,
                ))
                total_lessons += 1

            total_courses += 1
            print(f"  追加: {ch['title']} ({len(ch['lessons'])}本)")

        db.session.commit()
        print(f"\n完了: コース {total_courses}件、レッスン {total_lessons}本 を登録しました")


if __name__ == "__main__":
    chapters = parse_csv(CSV_PATH)
    print(f"CSVから {len(chapters)} 章、合計 {sum(len(c['lessons']) for c in chapters)} 本を読み込みました\n")
    import_data(chapters)
