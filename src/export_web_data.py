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

            pos_df = df_all[df_all["voted_up"] == True]
            neg_df = df_all[df_all["voted_up"] == False]

            total = len(df_all)
            pos_count = len(pos_df)
            neg_count = len(neg_df)
            approval_rate = pos_count / total if total > 0 else 0.0

            # votes_up でソートしてサンプリング（なければ先頭N件）
            def sample_reviews(df: pd.DataFrame, n: int) -> list[str]:
                if df.empty:
                    return []
                if "votes_up" in df.columns:
                    df = df.sort_values("votes_up", ascending=False)
                texts = df["review_text_en"].dropna().tolist()
                return [t for t in texts[:n] if isinstance(t, str) and t.strip()]

            reviews_data[slug][lang] = {
                "approval_rate": round(approval_rate, 4),
                "pos_count":     pos_count,
                "neg_count":     neg_count,
                "positive":      sample_reviews(pos_df, sample_pos),
                "negative":      sample_reviews(neg_df, sample_neg),
            }

            logger.info(
                "%-25s | %-10s | pos=%3d  neg=%3d  rate=%.2f",
                title, lang, pos_count, neg_count, approval_rate,
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
