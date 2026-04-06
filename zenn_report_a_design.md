# Zenn記事A 分析設計書
## 「Steamレビューの批判文化マップ：LLMで解剖する国別ゲーム不満の構造」

**作成日：** 2026年4月4日  
**著者：** 阿部竜弥  
**公開目標：** 2026年5月16日（Zenn）  
**位置づけ：** 任天堂マーケティングデータアナリスト応募ポートフォリオ 記事①

---

## 1. 研究の問い

> 同じゲームに対して、言語圏（≒文化圏）によって「何に怒り、何を褒めるか」のトピック構造は異なるか。  
> そしてその傾向はゲームジャンルを超えて普遍的に存在するか。

### なぜこの問いか

ゲームのグローバル展開において、ローカライズや地域別マーケティング施策の設計は重要な課題である。しかし「どの文化圏がどんな点を重視するか」をデータで示した分析はほとんど存在しない。本分析はその空白を埋め、**「文化差を定量化して施策提案につなげる」** という一気通貫の流れを示す。

### 先行分析との差別化

| 一般的な分析 | 本分析 |
|---|---|
| 単一ゲームのポジ/ネガ分類 | 複数ゲーム×複数言語の横断比較 |
| 英語レビューのみ | 6言語圏を対象 |
| LDA等の教師なしトピックモデル | LLMによる意味的カテゴリ分類 |
| スコアの高低の可視化 | 「何に怒るか」の構造的パターン抽出 |
| 記述統計で終わる | 施策提案まで踏み込む |

---

## 2. データ設計

### 2-1. データソース

- **Steam公式レビューAPI**（無料・APIキー不要）
  - エンドポイント：`https://store.steampowered.com/appreviews/<appid>?json=1`
  - 主要取得フィールド：

```
review          # レビュー本文
language        # 投稿言語（文化圏の代理変数として使用）
voted_up        # ポジティブ/ネガティブ
playtime_forever  # 総プレイ時間（分）
timestamp_created # 投稿日時
votes_up        # 他ユーザーによる「参考になった」数
author.num_games_owned  # 所持ゲーム数（ヘビーユーザー判定用）
```

- **制約と対処：** Steam APIは「国コード」を返さない。代わりに`language`フィールドを「言語圏≒文化圏」の代理変数として使用する。この制約は「言語が文化的文脈を規定する」という前提のもとで分析上の限界として明示する。

### 2-2. 対象言語（6言語圏）

| 言語コード | 対応文化圏 | 選定理由 |
|---|---|---|
| `japanese` | 日本 | 任天堂のコア市場・国内訴求の核 |
| `english` | 英語圏（米・英・豪） | Steam最大レビューボリューム |
| `schinese` | 中国（簡体字） | Steamユーザー数世界最大 |
| `russian` | ロシア・東欧 | Steam上位ユーザー層・批判的とされる |
| `german` | ドイツ・欧州 | 欧州圏代表・厳格なレビュー文化 |
| `koreana` | 韓国 | 東アジア内での日本との比較対象 |

### 2-3. 対象ゲーム（5タイトル）

ジャンルをまたぐことで「文化差がジャンルに依存するか、それとも普遍的か」を検証できる設計にする。

| タイトル | ジャンル | appid | 選定理由 |
|---|---|---|---|
| Dark Souls III | アクションRPG | 374320 | 日本産・難易度批判が国際的に多い |
| Stardew Valley | インディー農場 | 413150 | ポジティブ多め・文化差が出やすい |
| Counter-Strike 2 | 競技FPS | 730 | 批判が激しい・言語圏ごとに不満内容が異なると予想 |
| Cyberpunk 2077 | オープンワールドRPG | 1091500 | 大型炎上経験あり・回復過程の比較も可能 |
| Minecraft | サンドボックス | 1672970 | 全年齢・最も文化的背景が多様なユーザー層 |

### 2-4. 取得件数設計

- 各ゲーム × 各言語：**ネガティブレビュー200件 ＋ ポジティブレビュー100件** を目安
- 合計：5ゲーム × 6言語 × 300件 ＝ 最大 **9,000件**
- ネガティブを多めに取得する理由：批判の構造を見るのが主目的のため

---

## 3. 分析パイプライン

```
① データ取得（今週末 4/5〜4/6）
        ↓
② 前処理・翻訳（4/7〜4/13）
        ↓
③ LLMによるカテゴリ分類（4/14〜4/20）
        ↓
④ 集計・可視化（4/21〜4/27）
        ↓
⑤ 考察・施策提案・執筆（5/1〜5/11）
        ↓
⑥ Zenn公開（5/16）
```

---

## 4. 各ステップの詳細

### Step 1：データ取得

**使用ライブラリ：** `steamreviews`（`pip install steamreviews`）または `requests` で直接叩く

```python
import requests
import json
import time

def get_reviews(appid, language, review_type='negative', num=200):
    """Steam APIからレビューを取得する"""
    url = f"https://store.steampowered.com/appreviews/{appid}"
    reviews = []
    cursor = '*'

    while len(reviews) < num:
        params = {
            'json': 1,
            'language': language,
            'review_type': review_type,  # 'negative' or 'positive'
            'purchase_type': 'all',
            'num_per_page': 100,
            'cursor': cursor,
            'filter': 'all',
        }
        res = requests.get(url, params=params)
        data = res.json()

        if not data.get('reviews'):
            break

        reviews.extend(data['reviews'])
        cursor = data.get('cursor', '')
        if not cursor:
            break
        time.sleep(1)  # レート制限対策

    return reviews[:num]

# 実行例
GAMES = {
    'dark_souls_3': 374320,
    'stardew_valley': 413150,
    'cs2': 730,
    'cyberpunk': 1091500,
    'minecraft': 1672970,
}
LANGUAGES = ['japanese', 'english', 'schinese', 'russian', 'german', 'koreana']
```

**出力形式：** `data/raw/{game}_{language}_{type}.json`

---

### Step 2：前処理・翻訳

**目的：** 全レビューを英語に統一し、LLMによる分類を可能にする

**翻訳方針：**
- 英語レビューはそのまま使用
- 非英語レビューはClaude API（`claude-sonnet-4-6`）で英訳
  - DeepL APIも選択肢だが、Claude APIはすでに業務で使用実績があり即活用可能
  - 1件あたりのプロンプト例：

```python
def translate_to_english(review_text: str, source_language: str) -> str:
    prompt = f"""
Translate the following {source_language} Steam game review to English.
Preserve the tone (criticism, sarcasm, enthusiasm) as faithfully as possible.
Output only the translated text, nothing else.

Review:
{review_text}
"""
    # Claude API呼び出し
    ...
```

**前処理内容：**
- 空レビュー・1語レビューの除去
- 絵文字・記号のみのレビューの除去
- 50文字未満のレビューは除外（内容が薄いため）
- プレイ時間0分のレビューは除外（実プレイなし）

**出力形式：** `data/processed/{game}_{language}_translated.csv`

---

### Step 3：LLMによるカテゴリ分類（分析の核心）

**なぜLDAでなくLLMか：**
LDAは単語の共起に基づくため「文化的期待との齟齬」のような意味的に複雑なカテゴリを抽出できない。LLMは文脈を理解してラベルを付与できるため、人間が解釈しやすいカテゴリ分類が可能。

**分類カテゴリ（8カテゴリ）：**

| カテゴリID | カテゴリ名 | 定義 |
|---|---|---|
| `tech` | 技術的問題 | バグ、クラッシュ、最適化不足、起動不可 |
| `balance` | バランス・難易度 | 難しすぎる、簡単すぎる、ゲームバランスへの不満 |
| `story` | ストーリー・世界観 | 物語、キャラクター、設定への批評 |
| `price` | 価格・コスパ | 高すぎる、DLC商法、セール待ち推奨 |
| `community` | コミュニティ・運営 | 運営対応、アップデート頻度、開発者への不満 |
| `ux` | UI/UX・操作性 | 操作性、チュートリアル、インターフェース |
| `volume` | コンテンツ量 | ボリューム不足、周回要素、エンドコンテンツ |
| `cultural` | 文化的期待との齟齬 | 地域固有の価値観・慣習との不一致（**独自カテゴリ**） |

**プロンプト設計：**

```python
CATEGORIES = {
    'tech': '技術的問題（バグ・クラッシュ・最適化）',
    'balance': 'バランス・難易度',
    'story': 'ストーリー・世界観・キャラクター',
    'price': '価格・コスパ・DLC商法',
    'community': 'コミュニティ・運営・開発者対応',
    'ux': 'UI/UX・操作性・チュートリアル',
    'volume': 'コンテンツ量・ボリューム・周回要素',
    'cultural': '文化的期待との齟齬（地域固有の価値観との不一致）',
}

def classify_review(review_text: str) -> list[str]:
    prompt = f"""
You are a game review analyst. Classify the following Steam game review into one or more of the categories below.
A review can belong to multiple categories. Return only a JSON array of matching category IDs.

Categories:
{json.dumps(CATEGORIES, ensure_ascii=False, indent=2)}

Review:
{review_text}

Output format: ["category_id1", "category_id2"]
Output only the JSON array, nothing else.
"""
    # Claude API呼び出し → JSONパース
    ...
```

**バッチ処理：** コスト削減のため1プロンプトに複数レビューをまとめるバッチ分類も検討

**出力形式：** `data/classified/{game}_{language}_classified.csv`

カラム構成：`game, language, review_text_en, voted_up, playtime_forever, categories(list), timestamp_created`

---

### Step 4：集計・可視化

#### 可視化①：言語×カテゴリ ヒートマップ（メイン図）

各言語圏でどのカテゴリのレビューが多いかを比率で表示。ゲームをまたいだ平均値を使う。

```python
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# 言語×カテゴリの出現率マトリクス
pivot = df.groupby('language')[CATEGORY_IDS].mean()

sns.heatmap(pivot, annot=True, fmt='.2f', cmap='YlOrRd',
            xticklabels=CATEGORY_NAMES, yticklabels=LANGUAGE_NAMES)
plt.title('批判カテゴリの言語圏別出現率（ネガティブレビュー）')
```

#### 可視化②：ゲームをまたいだ文化差の一貫性（ジャクソン係数）

各ゲームペアで「言語圏の批判傾向の一致度」を計算。「文化差がゲームジャンルに依存しない普遍的なものか」を検証する。

#### 可視化③：「文化的期待との齟齬」カテゴリの国別ランキング

独自カテゴリ`cultural`の出現率を言語圏でランキング化。どの文化圏が最もゲームへの「文化的なズレ」を感じているかを可視化。

#### 可視化④：ポジティブ/ネガティブ別の批判構造の違い

ネガティブレビューとポジティブレビューで言及カテゴリがどう異なるかを比較。「褒めるときは何を褒め、批判するときは何を批判するか」の文化差。

---

### Step 5：考察・施策提案

分析結果から、以下の観点で考察と施策提案を行う。

**考察の切り口：**
- 「日本語レビューはXXカテゴリが多く、英語圏はYYカテゴリが中心」という定量的事実の提示
- 「なぜその文化差が生まれるか」の定性的な解釈（ゲーム文化・消費者行動の違い）
- ゲームジャンルをまたいで一貫する文化差 vs. ジャンル固有の文化差の識別

**施策提案の方向性（例）：**
- 日本市場向け：〇〇カテゴリへの言及が多いため、発売前の△△コミュニケーションを強化すべき
- 中国市場向け：価格・コスパへの言及が多い場合、セール戦略・バンドル販売の最適化
- ドイツ市場向け：技術的問題への言及が多い場合、リリース前のQAコミュニケーションを優先

**任天堂への接続：**
任天堂はグローバルにIPを展開しており、地域別のユーザーインサイトを活かしたコミュニケーション設計が求められる。本分析の手法は「プラットフォーム×キャラクターIPの地域別マーケティング施策設計」に直接応用可能。

---

## 5. スケジュール

| 期間 | タスク | 成果物 |
|---|---|---|
| 4/5〜4/6（今週末） | Steam APIでデータ取得・件数確認 | `data/raw/` 以下のJSONファイル群 |
| 4/7〜4/13 | 前処理・翻訳パイプライン構築・実行 | `data/processed/` 以下のCSV |
| 4/14〜4/20 | LLMカテゴリ分類パイプライン構築・実行 | `data/classified/` 以下のCSV |
| 4/21〜4/27 | 集計・可視化・EDA | グラフ・図表一式 |
| 5/1〜5/11 | 考察・施策提案・Zenn原稿執筆 | 原稿（Markdown） |
| 5/12〜5/15 | 推敲・図表最終調整・公開準備 | 最終稿 |
| **5/16** | **Zenn公開★** | **公開済み記事URL** |

---

## 6. 技術スタック

| 役割 | ツール |
|---|---|
| データ取得 | `requests` / `steamreviews` |
| データ処理 | `pandas`, `numpy` |
| 翻訳 | Claude API（`claude-sonnet-4-6`） |
| カテゴリ分類 | Claude API（`claude-sonnet-4-6`） |
| 可視化 | `seaborn`, `matplotlib`, `plotly` |
| 環境管理 | `poetry` or `venv` |
| バージョン管理 | GitHub（公開リポジトリ） |
| 記事公開 | Zenn |

---

## 7. リポジトリ構成（予定）

```
steam-review-culture-analysis/
├── README.md
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_translation.ipynb
│   ├── 03_llm_classification.ipynb
│   └── 04_visualization.ipynb
├── src/
│   ├── fetch_reviews.py
│   ├── translate.py
│   ├── classify.py
│   └── visualize.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── classified/
├── figures/
└── pyproject.toml
```

---

## 8. 限界・留意点（記事内で明示する）

- `language`フィールドはユーザーの設定言語であり、居住国と一致しない場合がある
- 翻訳精度によってカテゴリ分類の精度が影響を受ける（特に慣用表現・スラング）
- Steam利用者はゲーマーに偏っており、国全体の消費者像を代表しない
- レビュー投稿率はゲームや言語圏によって異なるため、サンプルサイズの差に注意
- LLMによる分類は再現性が完全でない（温度パラメータの設定と複数回試行の一致率を確認する）

---

## 9. 記事構成（Zenn）

```
0. はじめに：「同じゲームなのに、なぜ国によって評価が変わるのか？」
1. 分析の設計と方法
2. データ取得：Steam APIで6言語のレビューを収集する
3. LLMで批判カテゴリに分類する（プロンプト設計の工夫）
4. 結果①：言語圏×カテゴリのヒートマップ
5. 結果②：文化差はジャンルを超えて普遍的か
6. 結果③：「文化的期待との齟齬」はどの国で最も多いか
7. 考察：なぜこの差が生まれるのか
8. ゲームマーケティングへの示唆（施策提案）
9. まとめと今後の展望
```

---

*本設計書は随時更新する。分析過程で発見した知見は適宜反映する。*
