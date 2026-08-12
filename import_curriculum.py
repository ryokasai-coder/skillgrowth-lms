# -*- coding: utf-8 -*-
"""
デジタルマーケティング研修（全10章・180動画）を投入するスクリプト。

構造:
  カリキュラム（category） = デジタルマーケティング研修
  各章                     = Course（例: 第1章：SNS基礎理解）
  各動画                   = Lesson（video_url にYouTube URL）

冪等: 既に同名のコース／レッスンがあればスキップ（重複作成しない）。
再実行しても安全。動画の長さ(duration)は0のままでよく、受講者が初回再生した
時点でプレイヤーから実際の長さが記録される（set_duration の write-once）。

使い方（PythonAnywhereのBashコンソール）:
  cd ~/lms-project
  source ~/.virtualenvs/lms-venv/bin/activate
  export LMS_DATABASE_URI="sqlite:////home/skillgrowth/lms-project/instance/lms.db"
  python import_curriculum.py
"""
import re
import sys

sys.path.insert(0, '.')
from app import app, db, Course, Lesson

CURRICULUM = 'デジタルマーケティング研修'
TRAINING_TYPE = 'eラーニング'
PASS_SCORE = 80

# ユーザー提供の原文をそのまま貼り付け（章見出し → 「タイトル」行 → URL行 の繰り返し）
RAW = r"""
第1章：SNS基礎理解
１．SNS運用が企業成長に与える影響
https://youtu.be/ErZXpWz6A68
２．集客 / 採用 / 認知 / 信頼 の違い
https://youtu.be/eIT1lLKp-FU
３．TikTok / Instagram / YouTube の役割比較
https://youtu.be/5jBVjS2rGMg
４．SNSアルゴリズムの本質（推薦構造）
https://youtu.be/XESlHNO6gOY
５．なぜ“最初の3秒”で勝負が決まるのか
https://youtu.be/y-HLjTzMby4
６．視聴維持率（リテンション）を制する
https://youtu.be/sn_LooDpm_4
７．エンゲージメントと拡散の関係
https://youtu.be/6c4u7KKAl1s
８．「情報ではなく感情が動く」理由
https://youtu.be/KanORlyp4Z0
９．信頼は接触頻度 × 文脈で生まれる
https://youtu.be/GOFdlZ7i8eQ
１０．認知ではなく“思い出させる”設計
https://youtu.be/qzcF1S6FoQA
１１．SNSは「比較の場」である
https://youtu.be/9wivsaMOw2I
１２．バズは再現不可だが再生は再現できる
https://youtu.be/P-Y0JqDZq70
１３．数ではなく改善の質が伸びを決める
https://youtu.be/QRpJ4ksf8AA
１４．SNS運用に必要な思考・習慣・姿勢
https://youtu.be/qe4mMGijCiY
１５．自社アカウントの目標設定・方向性定義
https://youtu.be/w9dZI0XIR28
第2章：マーケティング基礎
１６．STP分析（誰に / 何を / なぜ届けるか）
https://youtu.be/M9sJXvLgaas
１７．ペルソナ設計と「心の声」抽出法
https://youtu.be/SzX-R9gnYcE
１８．顧客の“本当の悩み”を言語化する
https://youtu.be/ZSujx84aHPQ
１９．選ばれる理由（Value Proposition）設計
https://youtu.be/ChCwdMCu5ko
２０．カスタマージャーニーの整理
https://youtu.be/DH_LToy_0b0
２１．競合分析：同業ではなく比較対象を見る
https://youtu.be/Ik_3fYJR61Q
２２．機能価値と情緒価値
https://youtu.be/JtzORy0gWNM
２３．ストーリーがブランドを作る
https://youtu.be/u7iEWTu-QoY
２４．SNS→LINE→成約の導線設計
https://youtu.be/JwlUrhgJt4I
２５．オファー設計（提案の魅力を最大化）
https://youtu.be/Q0MIldPoFRc
２６．抵抗・不安・疑念の除去トーク
https://youtu.be/eaObvPZy9JE
２７．ファン化は好かれることではなく理解されること
https://youtu.be/5dGq4h9UqoA
２８．共感を生む世界観の作り方
https://youtu.be/qYXxTW5Rusc
２９．「言いたいこと」ではなく「伝わる言葉」
https://youtu.be/gjOPiIpWbls
３０．一貫性のあるブランドトーン設計
https://youtu.be/zhcobvtpVJw
第3章：企画構造（短縮版）
３１．企画は「目的 × 相手 × 感情」で決まる
https://youtu.be/3eZ4pCqg6DY
３２．コンテンツ5分類（バズ / 価値 / 共感 / 教育 / ストーリー）
https://youtu.be/yf2DHk9-f6w
３３．「刺さる一言」から逆算する企画思考
https://youtu.be/x-4NLnp4StI
３４．共感フレーズを生む技法
https://youtu.be/83NlFuJBNvs
３５．課題→解決→変化（教育系の基本構造）
https://youtu.be/3zug5dt9OvQ
３６．１テーマ→３０本に展開する抽象化思考
https://youtu.be/kdHNPWgEy6U
３７．シリーズ化で世界観を作る
https://youtu.be/dvE3n2NF29Q
３８．個人ストーリーの物語化（過去→葛藤→突破→今）
https://youtu.be/tiBK3K7fZ1Q
３９．企画→台本の“意図言語化”作業
https://youtu.be/f-dGO4XnLMQ
４０．企画チェックリストと品質基準
https://youtu.be/AmUtPmrbrYI
第3.5章：リサーチ実践
４１．SNSは“制作”ではなく“観察”から始まる
https://youtu.be/lifi9-XEC28
４２．TikTokリサーチ：バズ構造の抽出法
https://youtu.be/PLY5SOLAs4U
４３．Instagramリール：文脈 × 世界観分析
https://youtu.be/CbCaG4jTiuc
４４．YouTube Shorts：遷移と引き延ばし設計
https://youtu.be/_T3fG4ZdE6E
４５．競合分析テンプレ：構造写経シートの使い方
https://youtu.be/YVisZoTWM_s
４６．Whisper × ChatGPTで文字起こし→要約→構造抽出
https://youtu.be/5sDPl_NCn3A
４７．初動３秒コレクションを習慣化する方法
https://youtu.be/9t3pV9Ssvr4
４８．コメント欄から“本当の悩み”を抽出する
https://youtu.be/BqhCH7AItL0
４９．リサーチ結果を台本に転写する手順
https://youtu.be/3FCYGGVLKvQ
５０．リサーチの習慣化スケジュール設計
https://youtu.be/YHVQUSBigOg
第4章：台本作成（AI活用）
５１．台本は「話す言葉」で書く
https://youtu.be/z55hN03A_eg
５２．黄金構造：５秒 → 結論 → 解説 → CTA
https://youtu.be/hK0fyN5dMlg
５３．感情を動かす語尾・間・強調
https://youtu.be/kWxwBylUl6Q
５４．心の声を代弁する言い回し
https://youtu.be/dwAh5DmNFt0
５５．比喩・事例化で理解を深くする
https://youtu.be/VbeoE-gFCGI
５６．弱さ・葛藤を使った共感形成
https://youtu.be/6hiHUQIVZJ8
５７．CTA文言２０パターン集
https://youtu.be/M7P9LOISoQg
５８．AI台本生成①：プロンプト基礎設計
https://youtu.be/wVtzpvNAUe0
５９．AI台本生成②：バズ型テンプレ
https://youtu.be/Fx5L9dqPXwI
６０．AI台本生成③：価値提供型テンプレ
https://youtu.be/VR4D4fdKS_c
６１．AI台本生成④：共感・ストーリー型テンプレ
https://youtu.be/3W4CC7AGVXQ
６２．AI文体→人間味へ変換：口癖・間の挿入
https://youtu.be/PQzaFFMtFMw
６３．競合動画→文字起こし→台本化の自動フロー
https://youtu.be/H7EmaHMoLMI
６４．NotebookLMによる台本DB化と再学習
https://youtu.be/tLvRw5DFAI4
６５．キャラクター性（口癖・言い回し）の埋め込み
https://youtu.be/WkOUubYum5w
６６．抽象→具体への翻訳技術
https://youtu.be/xA-SQPUUF6A
６７．台本品質チェックリスト
https://youtu.be/jguq_y6z8Nk
６８．台本作成の時短（３０分→５分へ）
https://youtu.be/kIhEGw9O_jA
６９．台本DB設計（テンプレ化・タグ整理）
https://youtu.be/w6qlQsIj28s
７０．台本レビューと添削の基準
https://youtu.be/cgoZWgzrKUM
７１．台本を“資産”に変える保管体系
https://youtu.be/gRR9l84Djlw
７２．チーム台本共有のNotion構造
https://youtu.be/8PC9jp5oN3I
７３．作成担当 / 添削担当の役割分離
https://youtu.be/DKexBOJ28bM
７４．語彙・言い回しストック帳の作成
https://youtu.be/TwVWCuSezlI
７５．AI台本量産ラインの構築
https://youtu.be/O-cenBngl-4
第5章：撮影・収録
７６．撮影前準備（構成・台本・想定質問）
https://youtu.be/4DgVlW40j3Y
７７．カメラの基礎（iPhone / 一眼）
https://youtu.be/bkpoE34AeWI
７８．画角と余白の心理効果
https://youtu.be/QnlrJeaAeqQ
７９．光の位置と印象の変わり方
https://youtu.be/4XJMMCg6mbw
８０．表情と口角コントロール
https://youtu.be/zrxmpTIsViE
８１．声・抑揚・スピード調整
https://youtu.be/DQ0IPZrZn3M
８２．ジェスチャーと動きの付け方
https://youtu.be/4ywU3x3RQXE
８３．１カット or 複数カットの判断
https://youtu.be/oaFkGtlqvqk
８４．収録台本の読み合わせ
https://youtu.be/CEb0yNCuaxI
８５．撮影ディレクション
https://youtu.be/LjLsKmCH2EY
８６．演者の緊張を解く指導
https://youtu.be/3a7rcv2qJLY
８７．セルフ撮影セットの作り方
https://youtu.be/moZNDvA-zAU
８８．スタジオ撮影の導線設計
https://youtu.be/HKgZmpoR9Eg
８９．インタビュー構成撮影
https://youtu.be/MKzUeFeMJ4c
９０．Bロール映像の扱い
https://youtu.be/rtgH3G66PbU
９１．マイクと音声処理
https://youtu.be/8MVifHRuWFM
９２．撮影チェックリスト
https://youtu.be/QT_F9wakqnQ
９３．動画量産撮影スケジュール
https://youtu.be/J5dZDuA7-XE
９４．撮影と編集の連携
https://youtu.be/uZ1sZ5I_C_s
９５．撮影データの整理・保管
https://youtu.be/tq2crTx7Mvg
第6章：編集（AI活用）
９６．編集は「感情編集」
https://youtu.be/nlSY_-LvsA8
９７．視聴維持率を上げるカット基準
https://youtu.be/qI6c5n_8Ffc
９８．最初の３カットで惹きつける
https://youtu.be/2oRPfybww38
９９．伝わるテロップの作り方
https://youtu.be/fZuytjBLMaE
１００．CapCut操作基礎
https://youtu.be/HBfKWA1n4Cg
１０１．テンプレプロジェクト作成
https://youtu.be/GqkD8W-H3uo
１０２．BGM波形で抑揚作成
https://youtu.be/FpXDegzcRH4
１０３．SEで感情増幅
https://youtu.be/_KMiRJLw33g
１０４．トランジション最小化
https://youtu.be/Op_QzeJbY9g
１０５．画角と余白調整
https://youtu.be/dPnT60BIEMs
１０６．肌補正と露出調整
https://youtu.be/_1tkq74sZao
１０７．Whisperで自動文字起こし
https://youtu.be/NwsMJfbpqq8
１０８．ChatGPTで要約→テロップ化
https://youtu.be/NYK4Db3cckU
１０９．AI自動テロップ精度最適化
https://youtu.be/MpH8PEYurEE
１１０．リズム構造分析
https://youtu.be/1IizbI5BaUk
１１１．プリセット作成
https://youtu.be/LSX5nHfntQY
１１２．媒体別書き出し設定
https://youtu.be/3ImNVepVJ5k
１１３．編集作業の分業
https://youtu.be/OyKU8lqR2Is
１１４．１本３h→３０分短縮
https://youtu.be/gUI1MKFSTXM
１１５．AI編集９０％→人１０％仕上げ
https://youtu.be/qgh-oBsrseI
１１６．編集品質チェックリスト
https://youtu.be/iMBoBX88ktU
１１７．成功動画DB化
https://youtu.be/8ILx1BFAnXY
１１８．フィードバック運用
https://youtu.be/MU-vGvoa5io
１１９．編集体制構築
https://youtu.be/74WQZBY2ah0
１２０．編集自走化フロー
https://youtu.be/9klwMLH9NrE
第7章：投稿戦略
１２１．投稿戦略の基本方針
https://youtu.be/8mX6x1g2Pjs
１２２．媒体別投稿目的の違い
https://youtu.be/5ohpHJZ_zXc
１２３．アカウントコンセプト固定
https://youtu.be/0Qxnpob2hQs
１２４．フェーズ別投稿本数
https://youtu.be/tlPxn71PezQ
１２５．最適投稿時間分析
https://youtu.be/AzTbne0R4n4
１２６．ハッシュタグ設計
https://youtu.be/cFnhWCnnYDQ
１２７．キャプション心理設計
https://youtu.be/1DcmODnwXTE
１２８．サムネ／カバー統一世界観
https://youtu.be/xL5HjyWDdPk
１２９．コメントを増やす導線
https://youtu.be/dRMDXTiOvp8
１３０．保存を生む構成
https://youtu.be/E32JM6lfJrs
１３１．DM誘導の自然設計
https://youtu.be/SeK8_EtpWxM
１３２．伸びた投稿の再投稿戦略
https://youtu.be/HHzgWoDL2iA
１３３．動画リライト運用
https://youtu.be/aoRt2h36P-M
１３４．長期で伸びる基礎動画づくり
https://youtu.be/ZNsfrbGL8Oo
１３５．月間投稿スケジュール設計
https://youtu.be/Ax8JcdMinzA
１３６．予約投稿と運用自動化
https://youtu.be/YfcbL8-ma4c
１３７．コメント返信テンプレ
https://youtu.be/vt6B4S_6YDY
１３８．炎上回避のリスク管理
https://youtu.be/aF5VgHbVqls
１３９．アップデート適応
https://youtu.be/i-FaFAP8XMk
１４０．投稿PDCAフロー
https://youtu.be/IuwYtZmnYHc
第8章：分析・改善
１４１．意図を記録してから分析する
https://youtu.be/Kc8pvkrQi0w
１４２．KPI設計の順番
https://youtu.be/ySBa-TdFvbE
１４３．再生数の正しい評価
https://youtu.be/fBi1uOMB15M
１４４．視聴維持率分析
https://youtu.be/6_Pp4XIOij0
１４５．離脱ポイント改善
https://youtu.be/nrrce4IEFwo
１４６．伝わり方の微差調整
https://youtu.be/oNu_KGbB7Mg
１４７．意図→結果→仮説ログ
https://youtu.be/qK19LoY5Q0k
１４８．分析表テンプレ使用法
https://youtu.be/9ikDjSy9Yh4
１４９．成功要因の抽象化
https://youtu.be/5ScXfwLH7Vo
１５０．失敗要因の抽象化
https://youtu.be/adURX8g33Bw
１５１．投稿伸びの波の読み方
https://youtu.be/V4RJsJ6Wt4o
１５２．TikTokアナリティクス深掘り
https://youtu.be/cGbh6-Uw13s
１５３．Instagram Insights深掘り
https://youtu.be/GUwVbx0XNsc
１５４．YouTube Shorts分析
https://youtu.be/hlK0nLRhZRw
１５５．仮説検証高速化
https://youtu.be/qQuaAU81e-U
１５６．伸びるアカウントの共通点
https://youtu.be/3eXRQr51Kg8
１５７．分析会議設計
https://youtu.be/pRZXvBs_IMI
１５８．成果・数字ログの保存
https://youtu.be/89ztHE7ogOY
１５９．分析→制作反映手順
https://youtu.be/9w1fSKYDX5s
１６０．正しく分析を扱うマインド
https://youtu.be/LO9UX56bDig
第9章：フォロワーを動かす設計図
１６１．フォロワー心理と行動誘導
https://youtu.be/rUQOUHMDzCw
１６２．CTA設計と誘導最適化
https://youtu.be/wLUa34ZfvOg
１６３．SNS運用PDCA高速化
https://youtu.be/sy46CET3Yc8
１６４．初動3秒の重要性
https://youtu.be/0OXcsjfY5gw
１６５．SNS運用基礎応用
https://youtu.be/uv79YApmNA8
１６６．コンテンツ世界線設計
https://youtu.be/gfO1yA_BGA0
１６７．トレンド活用と投稿
https://youtu.be/9XxPNEsRAAM
１６８．ストーリーフォーミュラ活用法
https://youtu.be/FkBc43ZvTWw
１６９．UGC活用戦略
https://youtu.be/cpbs6GUoifU
１７０．SNS時代の保存・リピート戦略
https://youtu.be/YOMMnZCz_88
第10章：運用体制構築
１７１．SNS運用は習慣で勝つ
https://youtu.be/MppqFVtHwbg
１７２．運用チームの役割分担
https://youtu.be/rxGGwXg5I9o
１７３．Notion／Slack／Backlog 設計
https://youtu.be/ZcOtNTwgtlE
１７４．動画ストック管理
https://youtu.be/N9ekkNtoPYA
１７５．台本DB・編集DB・分析DB連結
https://youtu.be/zXb-lb--5LQ
１７６．改善会議フォーマット
https://youtu.be/L-DWR9iOcbw
１７７．外注・パートナー教育
https://youtu.be/xP6VKS1eC-A
１７８．KPIロードマップ
https://youtu.be/jomrSJWv_to
１７９．成果報告資料テンプレ
https://youtu.be/QqyifMHOLog
１８０．自走型SNSチームの完成とスケール戦略
https://youtu.be/fUYXWbVzRU8
"""

_NUM_PREFIX = re.compile(r'^[0-9０-９]+[．.．]\s*')


def _clean_title(t):
    return _NUM_PREFIX.sub('', t).strip()


def parse(raw):
    """章見出し → (タイトル, URL) の列、へ分解する。"""
    chapters = []       # [(course_title, [(lesson_title, url), ...]), ...]
    current = None
    pending_title = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('http'):
            if pending_title is not None and current is not None:
                current[1].append((_clean_title(pending_title), line))
            pending_title = None
        elif line.startswith('第') and '章' in line:
            current = (line, [])
            chapters.append(current)
            pending_title = None
        else:
            pending_title = line
    return chapters


def main():
    chapters = parse(RAW)
    total_lessons = sum(len(c[1]) for c in chapters)
    print(f'解析結果: {len(chapters)}章 / {total_lessons}動画')

    with app.app_context():
        created_courses = 0
        created_lessons = 0
        updated_lessons = 0
        for course_title, lessons in chapters:
            course = Course.query.filter_by(title=course_title).first()
            if not course:
                course = Course(
                    title=course_title,
                    category=CURRICULUM,
                    training_type=TRAINING_TYPE,
                    pass_score=PASS_SCORE,
                    is_published=True,
                )
                db.session.add(course)
                db.session.flush()
                created_courses += 1
            for order, (lesson_title, url) in enumerate(lessons, start=1):
                exists = Lesson.query.filter_by(course_id=course.id, title=lesson_title).first()
                if exists:
                    # 既存レッスンでもURL・順番がデータと違えば更新（URL修正の再適用に対応）
                    if exists.video_url != url or exists.order != order:
                        exists.video_url = url
                        exists.order = order
                        updated_lessons += 1
                    continue
                db.session.add(Lesson(
                    course_id=course.id,
                    title=lesson_title,
                    video_url=url,
                    order=order,
                ))
                created_lessons += 1
        db.session.commit()
        print(f'投入完了: 新規コース {created_courses} / 新規レッスン {created_lessons} / URL等更新 {updated_lessons}')
        print(f'現在の総コース数: {Course.query.count()} / 総レッスン数: {Lesson.query.count()}')


if __name__ == '__main__':
    main()
