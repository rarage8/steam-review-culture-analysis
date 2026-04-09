"""
Step 4.5: 分析結果をダッシュボード用JSONにエクスポートする
- data/processed/*_translated.csv を読み込む
- ゲーム × 言語ごとに好意率・レビューサンプルを集計
- web/data/games.json に出力（index.html が直接読み込む）

実データへの切り替え:
  index.html の fetch('data/mock.json') を fetch('data/games.json') に変更する
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from games_list import CORE_GAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── パス設定 ────────────────────────────────────────────────────────────────

ROOT          = Path(__file__).parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
WEB_DATA_DIR  = ROOT / "web" / "data"
WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── 定数 ───────────────────────────────────────────────────────────────────

LANGUAGES = ["japanese", "english", "schinese", "russian", "german", "koreana"]

# カードに表示するレビューのサンプル数
# votes_up（参考になった数）が多い順に取得する
SAMPLE_POS = 20
SAMPLE_NEG = 20

# ─── スラッグ変換（fetch_reviews.py と共通ロジック） ─────────────────────────


def _make_slug(title: str) -> str:
    return (
        title.lower()
        .replace(" ", "_")
        .replace(":", "")
        .replace("'", "")
        .replace(".", "")
        .replace("-", "_")
        .replace("__", "_")
    )


# ─── エクスポート処理 ────────────────────────────────────────────────────────


def export(
    game_list: list[tuple[str, int]] | None = None,
    sample_pos: int = SAMPLE_POS,
    sample_neg: int = SAMPLE_NEG,
) -> Path:
    """
    data/processed/ から集計して web/data/games.json を生成する。

    Returns
    -------
    Path : 出力ファイルパス
    """
    if game_list is None:
        game_list = list(CORE_GAMES.items())

    games_meta = [{"id": _make_slug(title), "title": title} for title, _ in game_list]
    reviews_data: dict = {}

    for title, _ in game_list:
        slug = _make_slug(title)
        reviews_data[slug] = {}

        for lang in LANGUAGES:
            # positive / negative の両 CSV を読み込んで結合
            frames: list[pd.DataFrame] = []
            for review_type in ["positive", "negative"]:
                path = PROCESSED_DIR / f"{slug}_{lang}_{review_type}_translated.csv"
                if not path.exists():
                    logger.debug("Not found: %s", path.name)
                    continue
                df = pd.read_csv(path, encoding="utf-8")
                frames.append(df)

            if not frames:
                logger.warning("No data for %s / %s", title, lang)
                continue

            df_all = pd.concat(frames, ignore_index=True)

            # voted_up が bool または 0/1 で入っているケースに対応
            df_all["voted_up"] = df_all["voted_up"].map(
                lambda x: bool(x) if isinstance(x, (bool, int, float)) else str(x).lower() == "true"
            )

            # ── 3段階感情分類 ──────────────────────────────────────
            # sentiment 列がある（classify.py 実行済み）場合はそれを優先。
            # なければ voted_up で二分割し neutral は空にする。
            has_sentiment = (
                "sentiment" in df_all.columns
                and df_all["sentiment"].notna().any()
                and (df_all["sentiment"].str.strip() != "").any()
            )

            if has_sentiment:
                pos_df = df_all[df_all["sentiment"] == "positive"]
                neu_df = df_all[df_all["sentiment"] == "neutral"]
                neg_df = df_all[df_all["sentiment"] == "negative"]
                # sentiment が空の行は voted_up にフォールバック
                unset = df_all[df_all["sentiment"].fillna("").str.strip() == ""]
                pos_df = pd.concat([pos_df, unset[unset["voted_up"] == True]], ignore_index=True)
                neg_df = pd.concat([neg_df, unset[unset["voted_up"] == False]], ignore_index=True)
            else:
                pos_df = df_all[df_all["voted_up"] == True]
                neg_df = df_all[df_all["voted_up"] == False]
                neu_df = pd.DataFrame()

            total     = len(df_all)
            pos_count = len(pos_df)
            neu_count = len(neu_df)
            neg_count = len(neg_df)
            approval_rate = pos_count / total if total > 0 else 0.0

            # ── レビュー前プレイ時間（分 → 時間） ───────────────────
            if "playtime_at_review" in df_all.columns:
                avg_pt = df_all["playtime_at_review"].dropna()
                avg_pt = avg_pt[avg_pt > 0]
                avg_playtime_h = round(float(avg_pt.mean()) / 60, 1) if len(avg_pt) > 0 else 0.0
            elif "playtime_forever" in df_all.columns:
                avg_pt = df_all["playtime_forever"].dropna()
                avg_pt = avg_pt[avg_pt > 0]
                avg_playtime_h = round(float(avg_pt.mean()) / 60, 1) if len(avg_pt) > 0 else 0.0
            else:
                avg_playtime_h = 0.0

            # ── サンプリング ─────────────────────────────────────────
            def sample_reviews(df: pd.DataFrame, n: int, col: str) -> list[str]:
                if df.empty or col not in df.columns:
                    return []
                if "votes_up" in df.columns:
                    df = df.sort_values("votes_up", ascending=False)
                texts = df[col].dropna().tolist()
                return [t for t in texts[:n] if isinstance(t, str) and t.strip()]

            reviews_data[slug][lang] = {
                "approval_rate":          round(approval_rate, 4),
                "pos_count":              pos_count,
                "neu_count":              neu_count,
                "neg_count":              neg_count,
                "avg_playtime_review_h":  avg_playtime_h,
                "positive":               sample_reviews(pos_df, sample_pos, "review_text_en"),
                "neutral":                sample_reviews(neu_df, sample_pos, "review_text_en"),
                "negative":               sample_reviews(neg_df, sample_neg, "review_text_en"),
                "positive_orig":          sample_reviews(pos_df, sample_pos, "review_text_orig"),
                "neutral_orig":           sample_reviews(neu_df, sample_pos, "review_text_orig"),
                "negative_orig":          sample_reviews(neg_df, sample_neg, "review_text_orig"),
            }

            logger.info(
                "%-25s | %-10s | pos=%3d  neu=%3d  neg=%3d  rate=%.2f  playtime=%.1fh",
                title, lang, pos_count, neu_count, neg_count, approval_rate, avg_playtime_h,
            )

    output = {"games": games_meta, "reviews": reviews_data}
    out_path = WEB_DATA_DIR / "games.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("=== Exported to %s ===", out_path)
    return out_path


# ─── エントリポイント ────────────────────────────────────────────────────────

if __name__ == "__main__":
    export()
    print("\nDone. To use real data, change index.html:")
    print("  fetch('data/mock.json')  →  fetch('data/games.json')")
