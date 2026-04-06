"""
Step 3: LLMによるカテゴリ分類
- data/processed/*_translated.csv からレビューを読み込む
- Claude API（claude-sonnet-4-6）を使って8カテゴリに多ラベル分類
- data/classified/{stem}_classified.csv に保存

出力カラム: game, language, review_type, review_text_en, review_text_orig,
           voted_up, playtime_forever, categories, timestamp_created
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import anthropic
import pandas as pd

from games_list import CORE_GAMES, GAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── パス設定 ────────────────────────────────────────────────────────────────

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
CLASSIFIED_DIR = Path(__file__).parent.parent / "data" / "classified"
CLASSIFIED_DIR.mkdir(parents=True, exist_ok=True)

# ─── 定数 ───────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
CLASSIFY_BATCH_SIZE = 20    # 1回のAPIコールで分類するレビュー数

LANGUAGES: list[str] = [
    "japanese",
    "english",
    "schinese",
    "russian",
    "german",
    "koreana",
]

# ─── カテゴリ定義（設計書 Step 3 準拠） ─────────────────────────────────────

CATEGORIES: dict[str, str] = {
    "tech":      "Technical issues (bugs, crashes, performance, optimization failures, launch problems)",
    "balance":   "Balance / difficulty (too hard, too easy, unfair mechanics, progression issues)",
    "story":     "Story / world / characters (narrative, lore, character writing, ending critique)",
    "price":     "Price / value (too expensive, DLC practices, not worth the cost, recommend waiting for sale)",
    "community": "Community / management (developer response, update frequency, toxic players, anti-cheat)",
    "ux":        "UI/UX / controls (interface, tutorial, keybindings, accessibility, controller support)",
    "volume":    "Content volume (too short, lack of endgame, replay value, missing features)",
    "cultural":  "Cultural mismatch (region-specific values, localization issues, cultural expectations not met)",
}

CATEGORY_IDS = list(CATEGORIES.keys())

_CATEGORY_JSON = json.dumps(CATEGORIES, indent=2)

# ─── 分類 ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a game review analyst. "
    "Classify Steam game reviews into one or more predefined categories. "
    "Return only valid JSON — no commentary, no markdown."
)

_CATEGORY_BLOCK = f"Categories:\n{_CATEGORY_JSON}"


def classify_batch(
    texts: list[str],
    client: anthropic.Anthropic,
    max_retries: int = 3,
) -> list[list[str]]:
    """
    英語レビューのリストを一括でカテゴリ分類する。

    Parameters
    ----------
    texts       : 分類対象の英語レビューテキストのリスト
    client      : Anthropic クライアント
    max_retries : APIエラー時のリトライ回数

    Returns
    -------
    list[list[str]] : 各レビューのカテゴリIDリスト（入力と同じ長さ）
                      分類失敗時は空リスト []
    """
    if not texts:
        return []

    numbered_block = "\n---\n".join(
        f"[{i + 1}]\n{text}" for i, text in enumerate(texts)
    )

    prompt = (
        f"{_CATEGORY_BLOCK}\n\n"
        "Classify each review below into zero or more categories.\n"
        "A review can belong to multiple categories.\n"
        "Output ONLY a JSON array of arrays — one inner array per review.\n"
        'Example for 3 reviews: [["tech","balance"], ["price"], ["story","cultural"]]\n\n'
        f"Reviews:\n{numbered_block}\n\n"
        "Output (JSON array of arrays only):"
    )

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

            # JSON配列を抽出
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                result: list[list[str]] = json.loads(match.group(0))
                if len(result) == len(texts) and all(
                    isinstance(r, list) for r in result
                ):
                    # 有効なカテゴリIDのみ残す
                    return [
                        [cat for cat in cats if cat in CATEGORY_IDS]
                        for cats in result
                    ]
            logger.warning(
                "Unexpected classification output (attempt %d/%d): %.100s...",
                attempt + 1, max_retries, raw,
            )
        except (json.JSONDecodeError, anthropic.APIError) as e:
            logger.warning(
                "Classification error (attempt %d/%d): %s", attempt + 1, max_retries, e
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    # フォールバック: 全て空リストで返す
    logger.error(
        "Classification failed for batch of %d reviews, returning empty lists", len(texts)
    )
    return [[] for _ in texts]


# ─── ファイル処理 ─────────────────────────────────────────────────────────────


def _make_slug(title: str) -> str:
    """タイトルをファイル名用スラッグに変換する。"""
    return (
        title.lower()
        .replace(" ", "_")
        .replace(":", "")
        .replace("'", "")
        .replace(".", "")
        .replace("-", "_")
        .replace("__", "_")
    )


def classify_file(
    processed_path: Path,
    client: anthropic.Anthropic,
    overwrite: bool = False,
) -> Path | None:
    """
    単一の processed CSV ファイルを分類して classified CSV に保存する。

    Returns
    -------
    Path | None : 保存先パス（スキップまたは失敗時は None）
    """
    # e.g. "dark_souls_iii_japanese_negative_translated.csv"
    #   → "dark_souls_iii_japanese_negative_classified.csv"
    stem = processed_path.stem  # ends with "_translated"
    out_stem = stem.replace("_translated", "_classified")
    out_path = CLASSIFIED_DIR / f"{out_stem}.csv"

    if out_path.exists() and not overwrite:
        logger.info("SKIP (exists): %s", out_path.name)
        return out_path

    try:
        df = pd.read_csv(processed_path, encoding="utf-8")
    except Exception as e:
        logger.error("Failed to load %s: %s", processed_path.name, e)
        return None

    if df.empty:
        logger.warning("Empty file: %s, skipping", processed_path.name)
        return None

    logger.info(
        "Classifying %-55s | %d rows",
        processed_path.name, len(df),
    )

    texts = df["review_text_en"].fillna("").tolist()
    all_categories: list[list[str]] = []
    total = len(texts)

    for i in range(0, total, CLASSIFY_BATCH_SIZE):
        batch = texts[i : i + CLASSIFY_BATCH_SIZE]
        cats = classify_batch(batch, client)
        all_categories.extend(cats)
        done = min(i + CLASSIFY_BATCH_SIZE, total)
        logger.info("  → classified %d / %d", done, total)
        time.sleep(0.3)  # レート制限対策

    # categories 列を JSON 文字列として保存（analyze.py で再パース）
    df["categories"] = [json.dumps(cats, ensure_ascii=False) for cats in all_categories]

    # 列順を analyze.py が期待する形に整える
    output_cols = [
        "game", "language", "review_type",
        "review_text_en", "review_text_orig",
        "voted_up", "playtime_forever",
        "categories", "timestamp_created",
    ]
    # 存在しない列はスキップ
    output_cols = [c for c in output_cols if c in df.columns or c == "categories"]
    df = df.reindex(columns=output_cols)

    df.to_csv(out_path, index=False, encoding="utf-8")
    logger.info("  → saved %d rows to %s", len(df), out_path.name)
    return out_path


# ─── 一括実行 ────────────────────────────────────────────────────────────────


def run_classification(
    game_list: list[tuple[str, int]] | None = None,
    languages: list[str] | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """
    指定ゲーム × 言語 の全 processed CSV ファイルを分類する。

    Parameters
    ----------
    game_list : [(タイトル, appid), ...] 省略時は CORE_GAMES
    languages : 言語コードリスト。省略時は LANGUAGES（6言語）
    overwrite : True なら既存ファイルを上書き
    """
    if game_list is None:
        game_list = list(CORE_GAMES.items())
    if languages is None:
        languages = LANGUAGES

    client = anthropic.Anthropic()
    saved: list[Path] = []

    total = len(game_list) * len(languages) * 2
    done = 0
    logger.info(
        "=== Classification start: %d games × %d languages × 2 types = %d files ===",
        len(game_list), len(languages), total,
    )

    for title, _ in game_list:
        slug = _make_slug(title)
        for lang in languages:
            for review_type in ["negative", "positive"]:
                processed_path = (
                    PROCESSED_DIR / f"{slug}_{lang}_{review_type}_translated.csv"
                )
                done += 1
                if not processed_path.exists():
                    logger.debug(
                        "[%d/%d] Not found: %s", done, total, processed_path.name
                    )
                    continue
                result = classify_file(processed_path, client, overwrite)
                if result:
                    saved.append(result)
                logger.info("[%d/%d] done", done, total)

    logger.info(
        "=== Classification complete: %d files saved to %s ===",
        len(saved), CLASSIFIED_DIR,
    )
    return saved


# ─── サマリー ────────────────────────────────────────────────────────────────


def summarize_classified() -> None:
    """data/classified/ の分類済みファイルを一覧表示する。"""
    files = sorted(CLASSIFIED_DIR.glob("*.csv"))
    if not files:
        print("No CSV files in data/classified/")
        return

    total_rows = 0
    print(f"\n{'File':<70} {'Rows':>6}")
    print("-" * 78)
    for f in files:
        try:
            df = pd.read_csv(f)
            n = len(df)
            total_rows += n
            print(f"{f.name:<70} {n:>6}")
        except Exception:
            print(f"{f.name:<70}  ERROR")
    print("-" * 78)
    print(f"{'TOTAL':<70} {total_rows:>6}")
    print(f"\nFiles: {len(files)}  |  Rows: {total_rows:,}")


# ─── エントリポイント ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Steam review classifier (Step 3)")
    parser.add_argument(
        "--mode",
        choices=["core", "full", "summary"],
        default="summary",
        help=(
            "core: コアゲームのみ処理  "
            "full: 全ゲーム処理  "
            "summary: 分類済みファイルの確認"
        ),
    )
    parser.add_argument("--overwrite", action="store_true", help="既存ファイルを上書き")
    args = parser.parse_args()

    if args.mode == "summary":
        summarize_classified()
    elif args.mode == "core":
        run_classification(
            game_list=list(CORE_GAMES.items()),
            overwrite=args.overwrite,
        )
    elif args.mode == "full":
        game_list = [(title, appid) for title, appid, *_ in GAMES]
        run_classification(
            game_list=game_list,
            overwrite=args.overwrite,
        )
