# -*- coding: utf-8 -*-
"""
AIリスキリング研修（全13章・72動画）を投入するスクリプト。

章見出しは「基礎【第1章】」「【第3章】」「DX【第9章】」等の形式。
接頭語（基礎/実装/創造/DX/戦略）があればコース名に付ける:
  基礎【第1章】 → 第1章：基礎   /   【第3章】 → 第3章

冪等: 既存コース／レッスンはスキップ。既存でも表示順・URLはデータに合わせて更新。

使い方（PythonAnywhereのBashコンソール）:
  cd ~/lms-project && source ~/.virtualenvs/lms-venv/bin/activate
  export LMS_DATABASE_URI="sqlite:////home/skillgrowth/lms-project/instance/lms.db"
  python import_curriculum2.py
"""
import re
import sys

sys.path.insert(0, '.')
from app import app, db, Course, Lesson

CURRICULUM = 'AIリスキリング研修'
TRAINING_TYPE = 'eラーニング'
PASS_SCORE = 80

RAW = r"""
基礎【第1章】
1,生成AIの正体とLLMの仕組み
→https://youtu.be/ljb7lDFJm_c
2,2026年最新AI比較 (Gemini/Claude/GPT)
→https://youtu.be/U5p_h037GFU
3,Perplexity/Copilotによる検索革命
→https://youtu.be/E3Qbdo88048
4,AIが得意なこと・絶対させてはいけないこと
→https://youtu.be/VDUIJg1WnQ8
実装【第2章】
5,プロンプトの5大要素（深津式を超えて）
→https://youtu.be/6tmYA43GgWE
6,Few-shotとChain of Thought
→https://youtu.be/_doN1WyMliA
7,ゴールシークプロンプトの活用
→https://youtu.be/Lr5sZCJ-HqM
8,出力形式のコントロール (JSON/Markdown/表)
→https://youtu.be/R-NMDvrbiJM
【第3章】
9,メール業務の自動化（状況別5パターン）
→https://youtu.be/4okdoJzIi58
10,営業資料のストーリー構成作成
→https://youtu.be/Ot2WQowUsNU
11,1時間の会議を3分で要約する技術
→https://youtu.be/i9heo3NKuyU
12,業務マニュアル・SOPの自動生成
→https://youtu.be/5l1ssBHq-_M
13,刺さる求人票・スカウトメール作成
 →https://youtu.be/_vq0gIyManc
14,社内周知・プレスリリースの初稿作成
→https://youtu.be/fNtkS6p3Iz8
15,長文ドキュメントの校正とリライト
→https://youtu.be/ofgHUwaZ8dk
16,多言語翻訳とローカライズの注意点
→https://youtu.be/M5Uz8WBBhbs
【第4章】
17,AIによる市場調査・トレンド分析
→https://youtu.be/SW15QSrM71o
18競合分析とSWOT分析の自動生成
→https://youtu.be/Dt5eBvI0158
19,超詳細ペルソナ設計と行動シナリオ
→https://youtu.be/3b07xPDsdc4
20,USP（独自の強み）の抽出と差別化
→https://youtu.be/8xSUOwfELX8
21,アイデア量産（ブレスト）の無限発想術
→https://youtu.be/c_sqnWveldg
22,顧客インタビューの擬似シミュレーション
→https://youtu.be/1vc9ik9Cocs
23,データの可視化とグラフ解釈
→https://youtu.be/3ugK0jDumGA
【第5章】
24,日報・週報の自動構造化
→https://youtu.be/E1fm1idpmsU
25,プロジェクトのタスク分解技術
→https://youtu.be/sWR7J_3AmPI
26業務フロー図（Mermaid）の自動生成
→https://youtu.be/Yzqlkn2h61U
27,マインドマップによる思考整理
→https://youtu.be/rB9quoS1_0w
28,社内ナレッジのAI整備術
→https://youtu.be/b58JSjIwBY8
29,カスタマーサポート用FAQ自動作成
→https://youtu.be/CAvNSTp4DY8
創造【第6章】
30,DALL-E 3による画像生成の基本
→https://youtu.be/XTnkmnChBnA
31,Midjourneyによるプロ級ビジュアル
→https://youtu.be/iR5xkAJ2b3Y
32,写真編集・背景削除のAI効率化
→https://youtu.be/MGEKWqU7deU
33,Canva×AIによるバナー量産
→https://youtu.be/4_owlNtmZ40
34プレゼン資料のビジュアル化戦略,
https://youtu.be/s6kozY65XDI
【第7章】
35,動画用AI台本と構成案の作成
→https://youtu.be/8VcWr1MjBA0
36,Vrewによる爆速字幕・カット編集
→https://youtu.be/Fj9KxHNhrlA
37,AIナレーションの選定と演出
→https://youtu.be/aemfha_L0hA
38,SNS用ショート動画の量産フロー
→https://youtu.be/dS4vUUq2xGI
【第8章】
39,Instagram投稿のAI設計術
→https://youtu.be/vTTyjWi1pTk
40,TikTok/Reelsのトレンド解析と適用
→https://youtu.be/Gkhb0aXlqdY
41,LINE公式アカウントの運用自動化
→https://youtu.be/xMxoynsIf0c
42,AIによるコンテンツカレンダー作成
→https://youtu.be/y74Hf8mv5gk
DX【第9章】
43,業務分解とAI接続の判断基準
→https://youtu.be/kmcID3QXb_I
44,AI接続の基本パターン（RAG/API）
→https://youtu.be/ywuyV1NEIW0
45,既存業務フローへのAI組み込み実践
→https://youtu.be/628kYPE3R6w
【第10章】
46,生成AI時代の情報漏洩リスクと対策
→https://youtu.be/LamART4euNg
47,社内利用ガイドラインの策定
→https://youtu.be/VWRfIi2frtM
48,プロンプト資産の管理と共有
→https://youtu.be/ssOH60g4LC0
【第11章】
49,【営業】見込み客リストの自動生成
→https://youtu.be/FWuyRme_VFQ
50,【営業】パーソナライズDMの自動作成
→https://youtu.be/NvRqYSkxXLI
51,【営業】商談フェーズ別のアドバイスAI
→https://youtu.be/ErcAzxM0wDM
52,【バックオフィス】契約書チェックのAI活用
→https://youtu.be/X4bgmwEBA5o
53,【バックオフィス】経費精算・仕訳の自動化
→https://youtu.be/5nWXmv_rWVA
54,【バックオフィス】社内問い合わせの自動回答
→https://youtu.be/-OhaymKNQxo
55,【マーケ】広告コピーのABテスト生成
→https://youtu.be/jyaZZHAdmnY
56,【マーケ】Webサイトの改善提案
→https://youtu.be/AoqjZThG-nI
57,【マーケ】オウンドメディアの記事量産
→https://youtu.be/_NKgCBp1wtQ
58,【採用】求人要件の定義とスカウト文作成
→https://youtu.be/uM4r7QdauPQ
59,【採用】候補者レジュメのスクリーニング
→https://youtu.be/niFzThTO4DQ
60,【採用】面接質問集と評価基準の作成
→https://youtu.be/rjqDWOp7LL0
61,【経営企画】市場環境分析の自動化
→https://youtu.be/ewEzXnph0cs
62,【経営企画】中期経営計画のドラフト作成
→https://youtu.be/8hadP6PLcKI
63,【経営企画】月次レポートの自動要約
→https://youtu.be/CQ853ebg5z0
戦略【第12章】
64,AI前提の仕事設計（AI-First Mindset）
→https://youtu.be/Z-OQVyoiIxI
65,人間にしかできない価値の再定義
→https://youtu.be/fVR9-Kw1R4o
66,AI時代のマネジメントと評価制度
→https://youtu.be/roThHuHd1sg
67,リスキリングを継続する仕組み作り
→https://youtu.be/KbXAsy4IyZY
【第13章】
68,AI導入の3ステップ（PoC/導入/定着）
→https://youtu.be/_ROu-scga40
69,AI活用のKPI・投資対効果の測定
→https://youtu.be/7U1d5l3XIbY
70,AIが定着しない理由と打開策
→https://youtu.be/1wkLGWMadRU
71,社内アンバサダーの育成と文化醸成
→https://youtu.be/i_J-68zxQLs
72,1年後の自社を描くロードマップ作成
→https://youtu.be/2A4cpg0Z_e0
"""

CHAPTER_RE = re.compile(r'^(.*?)【第([0-9０-９.]+)章】')
NUM_PREFIX = re.compile(r'^[0-9０-９]+[\s,，、.．]*')
URL_RE = re.compile(r'https?://\S+')


def _clean_title(t):
    t = NUM_PREFIX.sub('', t)
    return t.strip().rstrip('、,').strip()


def parse(raw):
    chapters = []
    current = None
    pending_title = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # URL行（→や空白始まり、または直接http）
        if 'youtu.be' in line or line.startswith('http') or line.startswith('→'):
            m = URL_RE.search(line)
            if m and pending_title is not None and current is not None:
                current[1].append((_clean_title(pending_title), m.group(0)))
            pending_title = None
            continue
        # 章見出し
        cm = CHAPTER_RE.match(line)
        if cm:
            phase = cm.group(1).strip()
            num = cm.group(2)
            title = f'第{num}章' + (f'：{phase}' if phase else '')
            current = (title, [])
            chapters.append(current)
            pending_title = None
            continue
        # それ以外はタイトル行
        pending_title = line
    return chapters


def main():
    chapters = parse(RAW)
    total = sum(len(c[1]) for c in chapters)
    print(f'解析結果: {len(chapters)}章 / {total}動画')
    with app.app_context():
        cc = cl = ul = 0
        for idx, (course_title, lessons) in enumerate(chapters, start=1):
            course = Course.query.filter_by(title=course_title, category=CURRICULUM).first()
            if not course:
                course = Course(title=course_title, category=CURRICULUM,
                                training_type=TRAINING_TYPE, pass_score=PASS_SCORE,
                                sort_order=idx, is_published=True)
                db.session.add(course)
                db.session.flush()
                cc += 1
            else:
                course.sort_order = idx
            for order, (lt, url) in enumerate(lessons, start=1):
                ex = Lesson.query.filter_by(course_id=course.id, title=lt).first()
                if ex:
                    if ex.video_url != url or ex.order != order:
                        ex.video_url = url
                        ex.order = order
                        ul += 1
                    continue
                db.session.add(Lesson(course_id=course.id, title=lt, video_url=url, order=order))
                cl += 1
        db.session.commit()
        print(f'投入完了: 新規コース {cc} / 新規レッスン {cl} / 更新 {ul}')
        print(f'AIリスキリング研修のコース数: '
              f'{Course.query.filter_by(category=CURRICULUM).count()}')
        print(f'全体: 総コース {Course.query.count()} / 総レッスン {Lesson.query.count()}')


if __name__ == '__main__':
    main()
