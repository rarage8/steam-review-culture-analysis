# Steam Review Culture Analysis

**Steamレビューの批判文化マップ：LLMで解剖する国別ゲーム不満の構造**

> 同じゲームに対して、言語圏（≒文化圏）によって「何に怒り、何を褒めるか」のトピック構造は異なるか。

Zenn記事①（2026年5月16日公開予定）のソースコードリポジトリ。
任天堂マーケティングデータアナリスト応募ポートフォリオ。

---

## 分析概要

| 項目 | 内容 |
|---|---|
| 対象ゲーム | 約100タイトル（アクション・FPS・RPG・インディーほか） |
| 対象言語圏 | 6言語（日本語・英語・中国語簡体字・ロシア語・ドイツ語・韓国語） |
| データソース | Steam Store Review API |
| 分析手法 | LLM（Claude API）による8カテゴリ分類 |
| 主な成果物 | 言語圏×カテゴリ ヒートマップ、好意率ランキング |

---

## パイプライン

```
① Steam APIでレビュー取得     src/fetch_reviews.py
        ↓
② 前処理・英語に翻訳          src/translate.py
        ↓
③ LLMで8カテゴリに分類        src/classify.py
        ↓
④ 集計・可視化                src/analyze.py
```

---

## セットアップ

```bash
# 依存関係インストール
pip install requests pandas seaborn matplotlib

# Step 1: コア5タイトルのレビュー取得
cd src
python fetch_reviews.py --mode core

# Step 1: 全99タイトル取得（時間がかかります）
python fetch_reviews.py --mode full

# 取得済みデータの確認
python fetch_reviews.py --mode summary

# Step 4: 可視化（生データのみ）
python analyze.py --raw-only
```

---

## リポジトリ構成

```
steam-review-culture-analysis/
├── src/
│   ├── games_list.py       # 対象ゲームリスト（99タイトル）
│   ├── fetch_reviews.py    # Steam APIレビュー取得
│   ├── translate.py        # 多言語→英語翻訳（Claude API）
│   ├── classify.py         # LLMカテゴリ分類（Claude API）
│   └── analyze.py          # 集計・可視化
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_translation.ipynb
│   ├── 03_llm_classification.ipynb
│   └── 04_visualization.ipynb
├── data/                   # .gitignore対象（ローカルのみ）
│   ├── raw/
│   ├── processed/
│   └── classified/
├── figures/                # .gitignore対象（ローカルのみ）
├── .gitignore
└── README.md
```

---

## 分析カテゴリ（8種）

| ID | カテゴリ名 | 定義 |
|---|---|---|
| `tech` | 技術的問題 | バグ・クラッシュ・最適化不足 |
| `balance` | バランス・難易度 | 難しすぎる・簡単すぎる |
| `story` | ストーリー・世界観 | 物語・キャラクター・設定 |
| `price` | 価格・コスパ | 高すぎる・DLC商法 |
| `community` | コミュニティ・運営 | 開発者対応・アップデート |
| `ux` | UI/UX・操作性 | チュートリアル・インターフェース |
| `volume` | コンテンツ量 | ボリューム不足・周回要素 |
| `cultural` | 文化的期待との齟齬 | 地域固有の価値観との不一致（独自カテゴリ） |

---

## 限界・留意点

- `language`フィールドはSteamの設定言語であり、居住国と一致しない場合がある
- Steam利用者はゲーマーに偏っており、国全体の消費者像を代表しない
- LLMによる分類は再現性が完全でない（温度パラメータの設定と一致率を確認）

---

*Author: 阿部竜弥 / 公開予定: 2026年5月16日 on Zenn*
