"""
Step 2: 前処理・翻訳
- data/raw/{game_slug}_{language}_{type}.json からレビューを読み込む
- 前処理（空・短レビューの除去、0プレイ時間の除去、記号のみ除去）
- 非英語レビューを Claude API（claude-sonnet-4-6）で英訳
- data/processed/{game_slug}_{language}_{type}_translated.csv に保存

出力カラム: game, language, review_type, review_text_en, review_text_orig,
           voted_up, playtime_forever, timestamp_created
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

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ─── 定数 ───────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
TRANSLATE_BATCH_SIZE = 10   # 1回のAPIコールで翻訳するレビュー数
MIN_REVIEW_LEN = 50         # 最低文字数（原文）
MIN_PLAYTIME_MIN = 1        # 最低プレイ時間（分）

LANGUAGES: list[str] = [
    "japanese",
    "english",
    "schinese",
    "russian",
    "german",
    "koreana",
]

LANGUAGE_NAMES: dict[str, str] = {
    "japanese": "Japanese",
    "english":  "English",
    "schinese": "Simplified Chinese",
    "russian":  "Russian",
    "german":   "German",
    "koreana":  "Korean",
}

# ─── 前処理 ──────────────────────────────────────────────────────────────────


def _is_valid_review(review: dict) -> bool:
    """レビューが分析対象として有効かどうかを判定する。"""
    text: str = review.get("review", "").strip()
    playtime: int = review.get("author", {}).get("playtime_forever", 0)

    # テキストが短すぎる（50文字未満）
    if len(text) < MIN_REVIEW_LEN:
        return False

    # プレイ時間が実質0分
    if playtime < MIN_PLAYTIME_MIN:
        return False

    # 絵文字・記号のみ（実際の単語文字が10未満）
    if len(re.findall(r"\w", text)) < 10:
        return False

    return True


# ─── 翻訳 ────────────────────────────────────────────────────────────────────


def translate_batch(
    texts: list[str],
    source_language: str,
    client: anthropic.Anthropic,
    max_retries: int = 3,
) -> list[str]:
    """
    テキストのリストを一括で英語に翻訳する。

    Parameters
    ----------
    texts           : 翻訳対象テキストのリスト
    source_language : 言語コード（"japanese" / "schinese" / ...）
    client          : Anthropic クライアント
    max_retries     : APIエラー時のリトライ回数

    Returns
    -------
    list[str] : 翻訳済みテキストのリスト（入力と同じ長さ）
                失敗時は原文をそのまま返す
    """
    if not texts:
        return []

    lang_name = LANGUAGE_NAMES.get(source_language, source_language)
    numbered_block = "\n---\n".join(
        f"[{i + 1}]\n{text}" for i, text in enumerate(texts)
    )

    prompt = (
        f"Translate the following {lang_name} Steam game reviews to English.\n"
        "Preserve the tone (criticism, sarcasm, enthusiasm, frustration) faithfully.\n"
        "Output ONLY a JSON array of translated strings, one per review, in the same order.\n"
        "Do not include any explanation or commentary.\n\n"
        f"Reviews:\n{numbered_block}\n\n"
        'Output format: ["translated text 1", "translated text 2", ...]'
    )

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

            # JSON配列を抽出（前後のマークダウン記法などを除去）
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                translated: list[str] = json.loads(match.group(0))
                if len(translated) == len(texts):
                    return translated
            logger.warning(
                "Unexpected translation output (attempt %d/%d): %.100s...",
                attempt + 1, max_retries, raw,
            )
        except (json.JSONDecodeError, anthropic.APIError) as e:
            logger.warning(
                "Translation error (attempt %d/%d): %s", attempt + 1, max_retries, e
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    # フォールバック: 原文をそのまま返す
    logger.error(
        "Translation failed for batch of %d reviews, using originals", len(texts)
    )
    return texts


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


def translate_file(
    raw_path: Path,
    client: anthropic.Anthropic,
    overwrite: bool = False,
) -> Path | None:
    """
    単一の raw JSON ファイルを前処理・翻訳して CSV に保存する。

    Returns
    -------
    Path | None : 保存先パス（スキップまたは失敗時は None）
    """
    stem = raw_path.stem  # e.g. "dark_souls_iii_japanese_negative"
    out_path = PROCESSED_DIR / f"{stem}_translated.csv"

    if out_path.exists() and not overwrite:
        logger.info("SKIP (exists): %s", out_path.name)
        return out_path

    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to load %s: %s", raw_path.name, e)
        return None

    meta = data["meta"]
    reviews: list[dict] = data["reviews"]
    language: str = meta["language"]
    game: str = meta["title"]
    review_type: str = meta["review_type"]

    logger.info(
        "Processing %-50s | lang=%-10s | raw=%d",
        raw_path.name, language, len(reviews),
    )

    # 前処理
    valid_reviews = [r for r in reviews if _is_valid_review(r)]
    logger.info(
        "  → after preprocessing: %d / %d valid", len(valid_reviews), len(reviews)
    )

    if not valid_reviews:
        logger.warning("No valid reviews in %s, skipping", raw_path.name)
        return None

    texts_orig = [r["review"].strip() for r in valid_reviews]

    # 翻訳（英語はそのまま、非英語は Claude API で翻訳）
    if language == "english":
        texts_en = texts_orig
    else:
        texts_en: list[str] = []
        total = len(texts_orig)
        for i in range(0, total, TRANSLATE_BATCH_SIZE):
            batch = texts_orig[i : i + TRANSLATE_BATCH_SIZE]
            translated = translate_batch(batch, language, client)
            texts_en.extend(translated)
            done = min(i + TRANSLATE_BATCH_SIZE, total)
            logger.info("  → translated %d / %d", done, total)
            time.sleep(0.5)  # レート制限対策

    # DataFrame 構築・保存
    rows = [
        {
            "game":              game,
            "language":          language,
            "review_type":       review_type,
            "review_text_en":    en,
            "review_text_orig":  orig,
            "voted_up":          r.get("voted_up"),
            "playtime_forever":  r.get("author", {}).get("playtime_forever", 0),
            "timestamp_created": r.get("timestamp_created"),
        }
        for r, orig, en in zip(valid_reviews, texts_orig, texts_en)
    ]
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False, encoding="utf-8")
    logger.info("  → saved %d rows to %s", len(df), out_path.name)
    return out_path


# ─── 一括実行 ────────────────────────────────────────────────────────────────


def run_translation(
    game_list: list[tuple[str, int]] | None = None,
    languages: list[str] | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """
    指定ゲーム × 言語 の全 raw JSON ファイルを前処理・翻訳する。

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
        "=== Translation start: %d games × %d languages × 2 types = %d files ===",
        len(game_list), len(languages), total,
    )

    for title, _ in game_list:
        slug = _make_slug(title)
        for lang in languages:
            for review_type in ["negative", "positive"]:
                raw_path = RAW_DIR / f"{slug}_{lang}_{review_type}.json"
                done += 1
                if not raw_path.exists():
                    logger.debug("[%d/%d] Not found: %s", done, total, raw_path.name)
                    continue
                result = translate_file(raw_path, client, overwrite)
                if result:
                    saved.append(result)
                logger.info("[%d/%d] done", done, total)

    logger.info(
        "=== Translation complete: %d files saved to %s ===", len(saved), PROCESSED_DIR
    )
    return saved


# ─── サマリー ────────────────────────────────────────────────────────────────


def summarize_processed() -> None:
    """data/processed/ の処理済みファイルを一覧表示する。"""
    files = sorted(PROCESSED_DIR.glob("*.csv"))
    if not files:
        print("No CSV files in data/processed/")
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

    parser = argparse.ArgumentParser(description="Steam review translator (Step 2)")
    parser.add_argument(
        "--mode",
        choices=["core", "full", "summary"],
        default="summary",
        help=(
            "core: コアゲームのみ処理  "
            "full: 全ゲーム処理  "
            "summary: 処理済みファイルの確認"
        ),
    )
    parser.add_argument("--overwrite", action="store_true", help="既存ファイルを上書き")
    args = parser.parse_args()

    if args.mode == "summary":
        summarize_processed()
    elif args.mode == "core":
        run_translation(
            game_list=list(CORE_GAMES.items()),
            overwrite=args.overwrite,
        )
    elif args.mode == "full":
        game_list = [(title, appid) for title, appid, *_ in GAMES]
        run_translation(
            game_list=game_list,
            overwrite=args.overwrite,
        )
