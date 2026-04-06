"""
Step 4: 集計・可視化
- 言語圏 × カテゴリ ヒートマップ
- ゲーム別・言語別の好意率（ポジティブ比率）
- 「どのゲームが各言語圏で最も好まれるか / 批判されるか」ランキング
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
import seaborn as sns

# ─── パス設定 ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_CLASSIFIED = ROOT / "data" / "classified"
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)

# ─── 日本語フォント設定（Windows） ──────────────────────────────────────────

def _setup_japanese_font() -> None:
    """Windowsで利用可能な日本語フォントをmatplotlibに設定する。"""
    candidates = ["Yu Gothic", "Meiryo", "MS Gothic", "IPAexGothic", "Noto Sans CJK JP"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            return
    # フォールバック: デフォルトのまま（文字化けする可能性あり）

_setup_japanese_font()

# ─── カテゴリ定義（設計書 Step 3 準拠） ─────────────────────────────────────

CATEGORIES: dict[str, str] = {
    "tech":      "技術的問題",
    "balance":   "バランス・難易度",
    "story":     "ストーリー・世界観",
    "price":     "価格・コスパ",
    "community": "コミュニティ・運営",
    "ux":        "UI/UX・操作性",
    "volume":    "コンテンツ量",
    "cultural":  "文化的期待との齟齬",
}
CATEGORY_IDS = list(CATEGORIES.keys())
CATEGORY_NAMES = list(CATEGORIES.values())

LANGUAGE_LABELS: dict[str, str] = {
    "japanese": "日本",
    "english":  "英語圏",
    "schinese": "中国",
    "russian":  "ロシア",
    "german":   "ドイツ",
    "koreana":  "韓国",
}

# ─── データロード ─────────────────────────────────────────────────────────────


def load_classified_data() -> pd.DataFrame:
    """
    data/classified/*.csv を全件読み込んで結合する。
    カラム: game, language, review_text_en, voted_up,
            playtime_forever, categories(list), timestamp_created
    """
    dfs: list[pd.DataFrame] = []
    for path in DATA_CLASSIFIED.glob("*.csv"):
        df = pd.read_csv(path)
        # categories カラムが文字列で保存されている場合はリストに変換
        if "categories" in df.columns and df["categories"].dtype == object:
            df["categories"] = df["categories"].apply(
                lambda x: json.loads(x) if isinstance(x, str) else x
            )
        dfs.append(df)

    if not dfs:
        raise FileNotFoundError(
            f"No CSV files found in {DATA_CLASSIFIED}. "
            "Run classify.py (Step 3) first."
        )
    return pd.concat(dfs, ignore_index=True)


def load_raw_sentiment() -> pd.DataFrame:
    """
    data/raw/*.json から voted_up・言語・ゲームのみ抽出した軽量 DataFrame を返す。
    分類前でも「好意率」だけ見たい場合に使う。
    """
    rows: list[dict] = []
    for path in DATA_RAW.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data["meta"]
        for r in data["reviews"]:
            rows.append(
                {
                    "game": meta["title"],
                    "language": meta["language"],
                    "review_type_fetched": meta["review_type"],
                    "voted_up": r.get("voted_up", None),
                    "playtime_forever": r.get("author", {}).get("playtime_forever", 0),
                    "votes_up": r.get("votes_up", 0),
                    "review_text": r.get("review", ""),
                }
            )
    if not rows:
        raise FileNotFoundError(f"No JSON files in {DATA_RAW}. Run fetch_reviews.py first.")
    return pd.DataFrame(rows)


# ─── 集計ヘルパー ─────────────────────────────────────────────────────────────


def expand_categories(df: pd.DataFrame) -> pd.DataFrame:
    """
    categories 列（リスト型）を one-hot エンコードして元 DataFrame に結合する。
    """
    one_hot = pd.DataFrame(
        {cat_id: df["categories"].apply(lambda cats: int(cat_id in cats))
         for cat_id in CATEGORY_IDS}
    )
    return pd.concat([df.reset_index(drop=True), one_hot], axis=1)


# ─── 可視化関数 ───────────────────────────────────────────────────────────────


def plot_category_heatmap(
    df: pd.DataFrame,
    voted_up: bool | None = False,
    title_suffix: str = "ネガティブレビュー",
    save: bool = True,
) -> None:
    """
    可視化①: 言語圏 × カテゴリ ヒートマップ

    Parameters
    ----------
    df          : load_classified_data() の戻り値
    voted_up    : None=全件, True=ポジ, False=ネガ
    title_suffix: グラフタイトルのサフィックス
    """
    subset = df if voted_up is None else df[df["voted_up"] == voted_up]
    subset = expand_categories(subset)

    pivot = subset.groupby("language")[CATEGORY_IDS].mean()
    pivot.index = pivot.index.map(lambda l: LANGUAGE_LABELS.get(l, l))
    pivot.columns = CATEGORY_NAMES

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".2f",
        cmap="YlOrRd",
        linewidths=0.5,
        ax=ax,
    )
    ax.set_title(f"批判カテゴリの言語圏別出現率（{title_suffix}）", fontsize=14, pad=12)
    ax.set_xlabel("カテゴリ")
    ax.set_ylabel("言語圏")
    plt.tight_layout()

    if save:
        out = FIGURES / f"heatmap_category_{title_suffix}.png"
        fig.savefig(out, dpi=150)
        print(f"Saved: {out}")
    plt.show()


def plot_approval_rate_by_game_language(
    df_raw: pd.DataFrame,
    top_n: int = 20,
    save: bool = True,
) -> None:
    """
    可視化②: ゲーム × 言語圏 別の好意率ヒートマップ
    「各言語圏でどのゲームが最も好かれ/嫌われているか」を俯瞰する。

    Parameters
    ----------
    df_raw  : load_raw_sentiment() の戻り値
    top_n   : 表示するゲーム数（全数が多い場合に絞り込む）
    """
    agg = (
        df_raw.groupby(["game", "language"])["voted_up"]
        .agg(["sum", "count"])
        .reset_index()
    )
    agg["approval_rate"] = agg["sum"] / agg["count"]

    pivot = agg.pivot(index="game", columns="language", values="approval_rate")
    pivot.columns = [LANGUAGE_LABELS.get(c, c) for c in pivot.columns]

    # レビュー数の少ないゲームを除外し、全言語の平均好意率で並べ替え
    pivot = pivot.dropna(thresh=3)  # 3言語以上のデータがあるゲームのみ
    pivot["mean"] = pivot.mean(axis=1)
    pivot = pivot.sort_values("mean", ascending=False).drop(columns="mean")
    pivot = pivot.head(top_n)

    fig, ax = plt.subplots(figsize=(10, max(6, len(pivot) * 0.4)))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        vmin=0,
        vmax=1,
        linewidths=0.4,
        ax=ax,
    )
    ax.set_title("ゲーム × 言語圏 別 好意率（ポジティブ率）", fontsize=14, pad=12)
    ax.set_xlabel("言語圏")
    ax.set_ylabel("ゲームタイトル")
    plt.tight_layout()

    if save:
        out = FIGURES / "approval_rate_game_language.png"
        fig.savefig(out, dpi=150)
        print(f"Saved: {out}")
    plt.show()


def plot_top_games_per_language(
    df_raw: pd.DataFrame,
    top_n: int = 5,
    save: bool = True,
) -> None:
    """
    可視化③: 言語圏ごとの「最も好まれるゲーム Top N」と「最も批判されるゲーム Top N」
    """
    agg = (
        df_raw.groupby(["game", "language"])["voted_up"]
        .agg(["sum", "count"])
        .reset_index()
    )
    agg = agg[agg["count"] >= 30]  # サンプル数30件未満は除外
    agg["approval_rate"] = agg["sum"] / agg["count"]

    languages = sorted(agg["language"].unique())
    n_langs = len(languages)

    fig, axes = plt.subplots(
        n_langs, 2, figsize=(16, n_langs * 3.5), squeeze=False
    )
    fig.suptitle("言語圏別 好意率 Top / Bottom ゲームランキング", fontsize=15, y=1.01)

    for row_idx, lang in enumerate(languages):
        subset = agg[agg["language"] == lang].sort_values("approval_rate")
        lang_label = LANGUAGE_LABELS.get(lang, lang)

        # Bottom (最も批判される)
        ax_bot = axes[row_idx][0]
        bottom = subset.head(top_n)
        bars = ax_bot.barh(bottom["game"], bottom["approval_rate"], color="#e74c3c")
        ax_bot.set_xlim(0, 1)
        ax_bot.set_title(f"{lang_label}: 最も批判されるゲーム", fontsize=11)
        ax_bot.set_xlabel("好意率")
        ax_bot.bar_label(bars, fmt="%.2f", padding=3)

        # Top (最も好まれる)
        ax_top = axes[row_idx][1]
        top = subset.tail(top_n).iloc[::-1]
        bars = ax_top.barh(top["game"], top["approval_rate"], color="#2ecc71")
        ax_top.set_xlim(0, 1)
        ax_top.set_title(f"{lang_label}: 最も好まれるゲーム", fontsize=11)
        ax_top.set_xlabel("好意率")
        ax_top.bar_label(bars, fmt="%.2f", padding=3)

    plt.tight_layout()

    if save:
        out = FIGURES / "top_games_per_language.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"Saved: {out}")
    plt.show()


def plot_cultural_category_by_language(
    df: pd.DataFrame,
    save: bool = True,
) -> None:
    """
    可視化④: 「文化的期待との齟齬」カテゴリの言語圏別出現率（設計書 可視化③ 相当）
    """
    df_neg = df[df["voted_up"] == False].copy()
    df_neg = expand_categories(df_neg)

    cultural_rate = (
        df_neg.groupby("language")["cultural"]
        .mean()
        .rename(index=LANGUAGE_LABELS)
        .sort_values(ascending=False)
    )

    fig, ax = plt.subplots(figsize=(8, 4))
    colors = ["#e74c3c" if v >= cultural_rate.median() else "#3498db"
              for v in cultural_rate]
    bars = ax.barh(cultural_rate.index[::-1], cultural_rate.values[::-1], color=colors[::-1])
    ax.set_xlabel("「文化的期待との齟齬」出現率")
    ax.set_title("どの言語圏が最も「文化的なズレ」を感じているか", fontsize=13)
    ax.bar_label(bars, fmt="%.3f", padding=3)
    plt.tight_layout()

    if save:
        out = FIGURES / "cultural_gap_by_language.png"
        fig.savefig(out, dpi=150)
        print(f"Saved: {out}")
    plt.show()


def plot_posneg_category_comparison(
    df: pd.DataFrame,
    language: str = "japanese",
    save: bool = True,
) -> None:
    """
    可視化⑤: ポジ vs ネガ でカテゴリ分布を比較（特定言語圏にフォーカス）
    """
    subset = df[df["language"] == language].copy()
    subset = expand_categories(subset)

    pos_rates = subset[subset["voted_up"] == True][CATEGORY_IDS].mean()
    neg_rates = subset[subset["voted_up"] == False][CATEGORY_IDS].mean()

    x = np.arange(len(CATEGORY_IDS))
    width = 0.35

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x - width / 2, pos_rates, width, label="ポジティブ", color="#2ecc71", alpha=0.8)
    ax.bar(x + width / 2, neg_rates, width, label="ネガティブ", color="#e74c3c", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(CATEGORY_NAMES, rotation=20, ha="right")
    ax.set_ylabel("出現率")
    lang_label = LANGUAGE_LABELS.get(language, language)
    ax.set_title(f"{lang_label}: ポジティブ vs ネガティブ レビューのカテゴリ分布", fontsize=13)
    ax.legend()
    plt.tight_layout()

    if save:
        out = FIGURES / f"posneg_comparison_{language}.png"
        fig.savefig(out, dpi=150)
        print(f"Saved: {out}")
    plt.show()


# ─── メインレポート ───────────────────────────────────────────────────────────


def run_full_analysis(use_classified: bool = True) -> None:
    """
    利用可能なデータに応じて可視化を一括実行する。

    Parameters
    ----------
    use_classified : True なら分類済みCSV（Step3完了後）、
                     False なら生データのみで実行できる可視化のみ
    """
    print("=== 生データ（好意率）の分析 ===")
    df_raw = load_raw_sentiment()
    print(f"Raw reviews loaded: {len(df_raw):,} rows")
    print(df_raw.groupby("language")["voted_up"].value_counts())

    plot_approval_rate_by_game_language(df_raw)
    plot_top_games_per_language(df_raw)

    if use_classified:
        print("\n=== 分類済みデータの分析 ===")
        df_classified = load_classified_data()
        print(f"Classified reviews loaded: {len(df_classified):,} rows")

        plot_category_heatmap(df_classified, voted_up=False, title_suffix="ネガティブ")
        plot_category_heatmap(df_classified, voted_up=True,  title_suffix="ポジティブ")
        plot_cultural_category_by_language(df_classified)

        for lang in ["japanese", "english", "schinese"]:
            try:
                plot_posneg_category_comparison(df_classified, language=lang)
            except Exception as e:
                print(f"Skip {lang}: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Steam review analyzer")
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="分類済みデータなしで生データのみ分析（Step1完了後に実行可能）",
    )
    args = parser.parse_args()

    run_full_analysis(use_classified=not args.raw_only)
