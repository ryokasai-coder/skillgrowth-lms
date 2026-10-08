# -*- coding: utf-8 -*-
"""
DX基礎編for店舗（全12章・64動画）を投入するスクリプト。

  カリキュラム（category） = DX基礎編for店舗
  各章                     = Course（例: 第1章：お店のためのDXの基礎知識）
  各動画                   = Lesson（video_url にYouTube URL）

タイトルはHP・受講案内と同じ新名称（YouTube側の動画タイトルは旧名称のまま）。
動画の長さ(duration_seconds)はDriveの元動画をffprobeで実測した値（YouTubeの長さと±3秒以内で一致を確認済み）。
合計 73637秒 = 20時間27分17秒（受講案内の標準学習時間）になるよう端数を調整済み。

冪等: 同名のコース／レッスンがあればURL・順番・長さだけ更新する。

使い方（VPS）:
  cd /opt/skillgrowth-lms && sudo -u lms .venv/bin/python import_dx.py
"""
import json
import sys

sys.path.insert(0, '.')
from app import app, db, Course, Lesson

CURRICULUM = 'DX基礎編for店舗'
TRAINING_TYPE = 'eラーニング'
PASS_SCORE = 80
EXPECTED_TOTAL = 73637

DATA = json.loads(r"""
[
 [
  "第1章：お店のためのDXの基礎知識",
  [
   [
    "DXとは何か",
    "https://youtu.be/XU0BnNcPxy4",
    1189
   ],
   [
    "なぜお店にDXが必要なのか",
    "https://youtu.be/OW9we0TZScU",
    1091
   ],
   [
    "IT化とDXの違い",
    "https://youtu.be/2qlheT1FXY4",
    1179
   ],
   [
    "国内外のDX成功事例",
    "https://youtu.be/O7BBji6OT3U",
    1173
   ],
   [
    "お店のDX推進の全体像",
    "https://youtu.be/D0Dc8J860Ow",
    1279
   ]
  ]
 ],
 [
  "第2章：クラウドツールで変わるお店の働き方",
  [
   [
    "クラウドサービスとは何か",
    "https://youtu.be/EYWFe6a2HEM",
    1109
   ],
   [
    "スタッフ連絡をチャットツールで効率化",
    "https://youtu.be/-rYGpDtnjeQ",
    1212
   ],
   [
    "ビデオ会議ツールの活用法",
    "https://youtu.be/5OEOebGKhnk",
    1186
   ],
   [
    "タスク・プロジェクト管理ツールの使い方",
    "https://youtu.be/KvmgrT2e7Bk",
    1188
   ],
   [
    "お店の資料管理と情報共有",
    "https://youtu.be/DkkEMRkyE7M",
    1169
   ],
   [
    "クラウドの種類（SaaS・PaaS・IaaS）",
    "https://youtu.be/BGheHqC1fHg",
    1150
   ],
   [
    "Google WorkspaceとMicrosoft 365",
    "https://youtu.be/oUWsXs_T94g",
    1212
   ],
   [
    "店舗外でも働ける環境づくり",
    "https://youtu.be/yuakKjrVvqQ",
    1179
   ]
  ]
 ],
 [
  "第3章：お店のデータ活用の基本",
  [
   [
    "データで考えるとは（勘と経験からの一歩）",
    "https://youtu.be/eDSXON5GxzI",
    1193
   ],
   [
    "データ分析ツール入門",
    "https://youtu.be/WY1tekCdH7w",
    1179
   ],
   [
    "グラフ・可視化の基本",
    "https://youtu.be/Nc-xtjMZ3s0",
    1185
   ],
   [
    "KPIとは何か",
    "https://youtu.be/457US74kLkc",
    1187
   ],
   [
    "収集・整理・分析の基本ステップ",
    "https://youtu.be/DcHRqgTZQUc",
    1174
   ],
   [
    "データにもとづくお店の経営",
    "https://youtu.be/w8aeXFZ8-zI",
    1097
   ]
  ]
 ],
 [
  "第4章：お店の業務効率化と自動化",
  [
   [
    "お店の業務の流れを見える化する",
    "https://youtu.be/LCV9_5BdOgk",
    1168
   ],
   [
    "ノーコードツールの活用",
    "https://youtu.be/XK3uYWnpPuU",
    1162
   ],
   [
    "RPA入門",
    "https://youtu.be/zXjKrHFmeMg",
    1073
   ],
   [
    "会議・レポートのAIツール活用",
    "https://youtu.be/oSrpZF_-4qU",
    1198
   ],
   [
    "事務作業のデジタル化",
    "https://youtu.be/kuHJHu9HML8",
    1185
   ]
  ]
 ],
 [
  "第5章：お店の情報セキュリティの基本",
  [
   [
    "情報セキュリティの基礎",
    "https://youtu.be/qjDSwdmQtrs",
    1215
   ],
   [
    "パスワード管理と多要素認証",
    "https://youtu.be/93H5wNM0t6E",
    1084
   ],
   [
    "フィッシング・マルウェア対策",
    "https://youtu.be/Q9LEMsuZhzs",
    1255
   ],
   [
    "個人情報保護法とお客様データの取り扱い",
    "https://youtu.be/4ytAPwWkXwc",
    1324
   ]
  ]
 ],
 [
  "第6章：AIとお店のDX人材",
  [
   [
    "AIとは",
    "https://youtu.be/PIDgu_9loTo",
    1358
   ],
   [
    "生成AIとは",
    "https://youtu.be/cpj0R_sZiGc",
    1222
   ],
   [
    "プロンプト入門",
    "https://youtu.be/NHC4u9oHobc",
    1321
   ],
   [
    "SNS・デジタルマーケティング入門",
    "https://youtu.be/hEaywOzKVL4",
    1254
   ],
   [
    "DX推進とお店の組織・文化づくり",
    "https://youtu.be/XGKt6qZuFXk",
    1276
   ],
   [
    "DX人材とスタッフのキャリア",
    "https://youtu.be/ls6LkyJsJ38",
    1304
   ]
  ]
 ],
 [
  "第7章：Claude入門（基本操作とプロンプト）",
  [
   [
    "Claudeとは・他の生成AIとの違い",
    "https://youtu.be/_zZFM_-LMd8",
    1009
   ],
   [
    "Claudeの基本操作と画面の見方",
    "https://youtu.be/GawvLm4tEHQ",
    1102
   ],
   [
    "プロンプトの基本と実践",
    "https://youtu.be/yDWGN7iNa_g",
    1270
   ],
   [
    "対話で答えを磨く実践テクニック",
    "https://youtu.be/64kCUThZ5cI",
    1193
   ],
   [
    "ファイル・資料を読み込ませて活用する",
    "https://youtu.be/d23YeEo-72w",
    1182
   ]
  ]
 ],
 [
  "第8章：お店の文章作成に活かす",
  [
   [
    "お客様・取引先へのメールを作る",
    "https://youtu.be/0pxAFGUoxDk",
    1148
   ],
   [
    "ミーティングの議事録・メモをまとめる",
    "https://youtu.be/M5oy0an4Okg",
    1194
   ],
   [
    "企画書・提案書のたたき台を作る",
    "https://youtu.be/b89BgdDkZ40",
    1194
   ],
   [
    "報告書・日報を効率化する",
    "https://youtu.be/qcwwJ8qIp_k",
    1233
   ],
   [
    "文章の推敲・校正・トーン調整",
    "https://youtu.be/0p7UXu_7364",
    1174
   ]
  ]
 ],
 [
  "第9章：情報整理と考える相棒にする",
  [
   [
    "長文資料を読み込んで要約する",
    "https://youtu.be/z9goIm-tiek",
    1201
   ],
   [
    "リサーチと情報整理",
    "https://youtu.be/ZjIgc0FWb-0",
    1138
   ],
   [
    "表・データを整理する",
    "https://youtu.be/xWqr3qn0ruw",
    1109
   ],
   [
    "アイデア出し・壁打ち相手にする",
    "https://youtu.be/dKF-dFq92Eg",
    1082
   ],
   [
    "翻訳・多言語対応",
    "https://youtu.be/GqqCm6GNDZM",
    1078
   ]
  ]
 ],
 [
  "第10章：資料作成と定型業務の効率化",
  [
   [
    "資料の構成を作る",
    "https://youtu.be/x9NaablZuoU",
    1063
   ],
   [
    "スライドの構成案・話す原稿を作る",
    "https://youtu.be/S0VdE2ylP4Y",
    1055
   ],
   [
    "ファイル・ドキュメント操作を任せる",
    "https://youtu.be/fAvcV25gFOs",
    1066
   ],
   [
    "表計算・集計の下ごしらえ",
    "https://youtu.be/arU-BjBIGKA",
    1025
   ],
   [
    "テンプレート・定型文を作る",
    "https://youtu.be/RSmepXZzYhs",
    1047
   ]
  ]
 ],
 [
  "第11章：お店の役割別の活用事例",
  [
   [
    "営業・集客での活用",
    "https://youtu.be/FZ0iYOPBEDo",
    1046
   ],
   [
    "事務作業での活用",
    "https://youtu.be/1La1FkoTxdU",
    1058
   ],
   [
    "販促・マーケティングでの活用",
    "https://youtu.be/2_tinNbcaW4",
    1068
   ],
   [
    "店長・マネジメントでの活用",
    "https://youtu.be/hkQenO7h9ww",
    1029
   ],
   [
    "採用・スタッフ育成での活用",
    "https://youtu.be/GkKVujWLVrk",
    1050
   ]
  ]
 ],
 [
  "第12章：定着と応用（使いこなしからお店全体へ）",
  [
   [
    "自分専用の使い方をつくる",
    "https://youtu.be/l6U-1JUZ6yU",
    1025
   ],
   [
    "よくある失敗と対処",
    "https://youtu.be/RnZ-JhLALwM",
    1002
   ],
   [
    "情報セキュリティと注意点",
    "https://youtu.be/1X9jN3qHE3Y",
    1005
   ],
   [
    "お店のチームで使い方を広げる",
    "https://youtu.be/zyauVfiVD8w",
    1041
   ],
   [
    "実践編まとめ・これからの学び",
    "https://youtu.be/XKaAvYbTlE8",
    1020
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
