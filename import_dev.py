# -*- coding: utf-8 -*-
"""
AI開発研修for店舗（全7章・66動画）を投入するスクリプト。

  カリキュラム（category） = DX基礎編for店舗
  各章                     = Course（例: 第1章：LLMO集客編（AI検索・地図検索に選ばれる店づくり））
  各動画                   = Lesson（video_url にYouTube URL）

タイトルはHP・受講案内と同じ新名称（YouTube側の動画タイトルは旧名称のまま）。
動画の長さ(duration_seconds)はDriveの元動画をffprobeで実測した値（YouTubeの長さと±3秒以内で一致を確認済み）。
合計 71570秒 = 19時間52分50秒（受講案内の標準学習時間）になるよう端数を調整済み。

冪等: 同名のコース／レッスンがあればURL・順番・長さだけ更新する。

使い方（VPS）:
  cd /opt/skillgrowth-lms && sudo -u lms .venv/bin/python import_dev.py
"""
import json
import sys

sys.path.insert(0, '.')
from app import app, db, Course, Lesson

CURRICULUM = 'AI開発研修for店舗'
TRAINING_TYPE = 'eラーニング'
PASS_SCORE = 80
EXPECTED_TOTAL = 71570

DATA = json.loads(r"""
[
 [
  "第1章：LLMO集客編（AI検索・地図検索に選ばれる店づくり）",
  [
   [
    "AIと地図検索に選ばれる店になる（LLMO×MEO入門）",
    "https://youtu.be/tX_jqi2veBw",
    980
   ],
   [
    "AIに引用される店になる（実践編）",
    "https://youtu.be/EXHGIkTl9xs",
    1015
   ],
   [
    "自店の現在地を知る（AI引用の棚卸し）",
    "https://youtu.be/_xl4hXJXKUw",
    860
   ],
   [
    "Googleビジネスプロフィールの徹底整備",
    "https://youtu.be/l-OmU7Ia1ZA",
    810
   ],
   [
    "サイトをAIに読ませる",
    "https://youtu.be/G5EZFtke4sg",
    796
   ],
   [
    "引用される文章術",
    "https://youtu.be/F9w1CyNj0QU",
    793
   ],
   [
    "一次情報とE-E-A-T",
    "https://youtu.be/YhHCWMnWKWk",
    809
   ],
   [
    "外部評価を設計する",
    "https://youtu.be/mVlr4CbtsdM",
    788
   ],
   [
    "狙うクエリの選定とAI別攻略",
    "https://youtu.be/t48IHMKTV_k",
    848
   ],
   [
    "計測・改善と質で回す運用",
    "https://youtu.be/07GhFMZAH70",
    840
   ]
  ]
 ],
 [
  "第2章：公式LINE×AI編",
  [
   [
    "なぜ今公式LINE×AIなのか",
    "https://youtu.be/L9ktl3k-6pE",
    811
   ],
   [
    "初期設計とツール選定",
    "https://youtu.be/pAjyiu5fnr0",
    808
   ],
   [
    "リッチメニューをAIで作る",
    "https://youtu.be/lV0LMMp_tk8",
    831
   ],
   [
    "友だちを増やす仕組み",
    "https://youtu.be/Ua5tdAFSq_8",
    701
   ],
   [
    "ステップ配信をAIで作る",
    "https://youtu.be/VcqMLvVVBtg",
    860
   ],
   [
    "配信文の量産と週1一斉配信",
    "https://youtu.be/DaOL1o8kMqs",
    692
   ],
   [
    "着座率・ドタキャン対策",
    "https://youtu.be/zTKOZgktZK4",
    681
   ],
   [
    "AIチャットボットで問い合わせ自動化",
    "https://youtu.be/CnCvBrn2hjE",
    710
   ],
   [
    "Lステップ・LINEハーネスをAIで構築",
    "https://youtu.be/uN-EUdiOc5o",
    865
   ],
   [
    "計測・改善と法令・運用",
    "https://youtu.be/IjtQ8c3orxc",
    852
   ]
  ]
 ],
 [
  "第3章：店舗運営オペレーション編",
  [
   [
    "店舗運営のどこをAIで効率化できるか",
    "https://youtu.be/9_eHGfTVLIw",
    708
   ],
   [
    "予約・問い合わせ対応の自動化",
    "https://youtu.be/sWHgVCDr_fU",
    641
   ],
   [
    "シフト作成をAIで",
    "https://youtu.be/yn0mjl7Tqug",
    604
   ],
   [
    "在庫・発注の管理と需要予測",
    "https://youtu.be/KTbJ5eF8Gxs",
    658
   ],
   [
    "マニュアル・手順書をAIで作る",
    "https://youtu.be/qOgRutvN5AA",
    672
   ],
   [
    "数値管理・売上分析をAIで",
    "https://youtu.be/-IG_Os65MiM",
    691
   ],
   [
    "経理・バックオフィスの効率化",
    "https://youtu.be/6BH_aGLrjtw",
    615
   ],
   [
    "スタッフ教育・OJTをAIで",
    "https://youtu.be/W66vPf82cYM",
    673
   ],
   [
    "クレーム・トラブル対応の準備",
    "https://youtu.be/4CzI_qwPl1Q",
    664
   ],
   [
    "運営の仕組み化と改善サイクル",
    "https://youtu.be/Ip_dSnG3WUI",
    711
   ],
   [
    "AI活用を店に定着させる",
    "https://youtu.be/b-axX-GYZC4",
    723
   ]
  ]
 ],
 [
  "第4章：SNS×AI深掘り編",
  [
   [
    "なぜ今店舗にSNS×AIなのか",
    "https://youtu.be/Lf7OksrH4L4",
    1344
   ],
   [
    "撮らずに作るショート動画（AIで台本から動画）",
    "https://youtu.be/KZfFUybMB8Q",
    1256
   ],
   [
    "伸びる型と業種別テンプレ",
    "https://youtu.be/KtByrdSn5KY",
    1185
   ],
   [
    "企画・投稿カレンダーをAIで作りきる",
    "https://youtu.be/np7x-3CPe8Q",
    1171
   ],
   [
    "キャプション＆ハッシュタグをAIで量産",
    "https://youtu.be/xdC-jQXHuFc",
    1163
   ],
   [
    "AI画像・バナー生成と商用利用の勘所",
    "https://youtu.be/yHF17g2WFvU",
    1187
   ],
   [
    "コメント・DMとファン化の自動化",
    "https://youtu.be/P_Y1_5Jxqzg",
    1063
   ],
   [
    "効果測定と改善サイクルをAIで回す",
    "https://youtu.be/0YabJ4NoD6c",
    1140
   ],
   [
    "媒体別攻略とGBP・MEO連携",
    "https://youtu.be/nMC9xFapENQ",
    1137
   ],
   [
    "コンプラ総まとめと運用の仕組み化",
    "https://youtu.be/rcWBGCu4WPI",
    1291
   ],
   [
    "生成AIでXのスレッド投稿を作る",
    "https://youtu.be/t9hHCydoZpg",
    1330
   ],
   [
    "AIでインバウンド向けショート動画を作る",
    "https://youtu.be/oL0XU81qTYQ",
    1608
   ]
  ]
 ],
 [
  "第5章：接客インバウンド編",
  [
   [
    "外国人客対応の現状診断と最初の多言語案内",
    "https://youtu.be/W_oWY-N4CxE",
    1653
   ],
   [
    "生成AIと音声翻訳を接客場面に割り当てる",
    "https://youtu.be/o5SB3zne-54",
    1650
   ],
   [
    "メニュー・POP・店内案内をAIで多言語化する",
    "https://youtu.be/vXfPMk9DkZg",
    1718
   ],
   [
    "接客フレーズ集と指差しシートで対面接客する",
    "https://youtu.be/1qqq383jb0Y",
    1733
   ],
   [
    "多言語FAQカードで同じ質問を減らす",
    "https://youtu.be/feQe9WeZRUs",
    1745
   ],
   [
    "問い合わせ・予約の多言語返信をAIで仕込む",
    "https://youtu.be/WVVKzHoxn48",
    1689
   ],
   [
    "外国語の口コミにAIで返信しマップ集客につなげる",
    "https://youtu.be/wlb8f1R_ftk",
    1668
   ],
   [
    "クレーム・トラブルの多言語対応をAIロールプレイで練習する",
    "https://youtu.be/lPaav2Q8UCA",
    1722
   ],
   [
    "多言語対応の事故を防ぐ点検体制をつくる",
    "https://youtu.be/9bHfx25Wwpo",
    1723
   ],
   [
    "業種別の実装と90日で定着させる運用計画",
    "https://youtu.be/S7kPLfCvM7k",
    1750
   ]
  ]
 ],
 [
  "第6章：採用育成編",
  [
   [
    "求人票をAIで作り直す",
    "https://youtu.be/VOXeGvts2ik",
    1728
   ],
   [
    "応募への即レスと面接日程の調整をAIで仕込む",
    "https://youtu.be/DxS4sVwWUVc",
    1771
   ],
   [
    "面接をAIで設計する",
    "https://youtu.be/bOBfW4JYxSQ",
    1776
   ],
   [
    "入社後1週間のオンボーディングとOJTをAIで作る",
    "https://youtu.be/3-WzFt_jfBY",
    1705
   ]
  ]
 ],
 [
  "第7章：開発編上級（Claude Codeによる業務自動化）",
  [
   [
    "セッションをグループで整理する",
    "https://youtu.be/mo8-CUqX7R4",
    887
   ],
   [
    "閉じても止まらない開発環境をつくる",
    "https://youtu.be/GuHr9ltNbYs",
    926
   ],
   [
    "スマホから開発を進められるようにする",
    "https://youtu.be/BTd-ImnT7FE",
    949
   ],
   [
    "定期チェックを自動化する",
    "https://youtu.be/5JnWXRwl0h8",
    1021
   ],
   [
    "イベントで自動実行する",
    "https://youtu.be/_7c0NpxrCK8",
    1130
   ],
   [
    "Chrome連携で業務操作を自動化する",
    "https://youtu.be/7E7s1aXQxYg",
    1029
   ],
   [
    "毎朝・毎週の業務を自動化する",
    "https://youtu.be/zEqEywQ-ZBM",
    979
   ],
   [
    "大きめの制作を一気通貫させる",
    "https://youtu.be/s2WOnFJjzKI",
    1036
   ],
   [
    "自分専用のレビュー役をつくる",
    "https://youtu.be/6cVznrth6IY",
    997
   ]
  ]
 ]
]
""")


def main():
    total = sum(sec for _c, ls in DATA for _t, _u, sec in ls)
    n = sum(len(ls) for _c, ls in DATA)
    assert total == EXPECTED_TOTAL, total
    print(f'解析結果: {len(DATA)}章 / {n}動画 / 合計 {total}秒')
    with app.app_context():
        created_c = created_l = updated_l = 0
        for idx, (course_title, lessons) in enumerate(DATA, start=1):
            course_sec = sum(sec for _t, _u, sec in lessons)
            course = Course.query.filter_by(title=course_title).first()
            if not course:
                course = Course(title=course_title, category=CURRICULUM,
                                training_type=TRAINING_TYPE, pass_score=PASS_SCORE,
                                sort_order=idx, is_published=True)
                db.session.add(course)
                db.session.flush()
                created_c += 1
            course.sort_order = idx
            course.total_hours = round(course_sec / 3600, 4)
            for order, (title, url, sec) in enumerate(lessons, start=1):
                les = Lesson.query.filter_by(course_id=course.id, title=title).first()
                if les:
                    if (les.video_url, les.order, les.duration_seconds) != (url, order, sec):
                        les.video_url, les.order, les.duration_seconds = url, order, sec
                        updated_l += 1
                    continue
                db.session.add(Lesson(course_id=course.id, title=title, video_url=url,
                                      order=order, duration_seconds=sec))
                created_l += 1
        db.session.commit()
        print(f'投入完了: 新規コース {created_c} / 新規レッスン {created_l} / 更新 {updated_l}')
        q = (db.session.query(Course.id).filter(Course.category == CURRICULUM))
        ids = [r[0] for r in q]
        got = sum(l.duration_seconds or 0 for l in Lesson.query.filter(Lesson.course_id.in_(ids)))
        print(f'DB上の {CURRICULUM}: {len(ids)}章 / 合計 {got}秒')


if __name__ == '__main__':
    main()
