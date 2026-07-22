"""
YouTubeから全レッスンの実際の動画時間を取得してDBを更新するスクリプト
duration_seconds が未設定（0）のレッスンのみ対象
"""
import re
import sys
import time
import requests
from app import app, db, Lesson

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def extract_video_id(url):
    if not url:
        return None
    if 'youtube.com/watch' in url:
        m = re.search(r'v=([^&]+)', url)
    elif 'youtu.be/' in url:
        m = re.search(r'youtu\.be/([^?]+)', url)
    else:
        return None
    return m.group(1) if m else None


def fetch_duration(video_id):
    try:
        url = f'https://www.youtube.com/watch?v={video_id}'
        r = requests.get(url, headers=HEADERS, timeout=10)
        m = re.search(r'"lengthSeconds":"(\d+)"', r.text)
        return int(m.group(1)) if m else None
    except Exception as e:
        print(f'  エラー: {e}')
        return None


def run():
    with app.app_context():
        # video_url が設定されている全レッスンを対象にする
        lessons = Lesson.query.filter(
            Lesson.video_url.isnot(None),
            Lesson.video_url != ''
        ).all()

        print(f'対象レッスン: {len(lessons)}件')
        updated = 0
        failed = 0

        for i, lesson in enumerate(lessons, 1):
            vid = extract_video_id(lesson.video_url)
            if not vid:
                print(f'[{i}/{len(lessons)}] スキップ（URL不正）: {lesson.title}')
                failed += 1
                continue

            sec = fetch_duration(vid)
            if sec and sec > 0:
                lesson.duration_seconds = sec
                lesson.duration_minutes = max(1, sec // 60)
                updated += 1
                m, s = sec // 60, sec % 60
                print(f'[{i}/{len(lessons)}] {lesson.title[:40]} → {m}分{s}秒')
            else:
                print(f'[{i}/{len(lessons)}] 取得失敗: {lesson.title[:40]}')
                failed += 1

            # YouTube への負荷軽減
            time.sleep(0.5)

            # 50件ごとにコミット
            if i % 50 == 0:
                db.session.commit()
                print(f'--- {i}件処理済み ---')

        db.session.commit()
        print(f'\n完了: 更新 {updated}件 / 失敗 {failed}件')


if __name__ == '__main__':
    run()
