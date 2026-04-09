"""
Step 1: Steam APIからレビューを取得する
設計書: data/raw/{game_slug}_{language}_{type}.json に保存
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
from pathlib import Path
from typing import Literal

import requests

from games_list import CORE_GAMES, GAME_MAP, GAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── 定数 ───────────────────────────────────────────────────────────────────

LANGUAGES: list[str] = [
    "japanese",
    "english",
    "schinese",
    "russian",
    "german",
    "koreana",
]

LANGUAGE_LABELS: dict[str, str] = {
    "japanese": "日本",
    "english":  "英語圏",
    "schinese": "中国（簡体字）",
    "russian":  "ロシア・東欧",
    "german":   "ドイツ・欧州",
    "koreana":  "韓国",
}

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

ReviewType = Literal["negative", "positive", "all"]

# ─── コア関数 ────────────────────────────────────────────────────────────────


def get_reviews(
    appid: int,
    language: str,
    review_type: ReviewType = "negative",
    num: int = 300,
    sleep_sec: float = 1.2,
) -> list[dict]:
    """
    Steam Store Review API からレビューを取得する。

    Parameters
    ----------
    appid       : SteamアプリID
    language    : 言語コード（"japanese" / "english" / "schinese" / ...）
    review_type : "negative" | "positive" | "all"
    num         : 最大取得件数
    sleep_sec   : リクエスト間隔（秒）

    Returns
    -------
    list[dict] : レビューオブジェクトのリスト（最大 num 件）
    """
    url = f"https://store.steampowered.com/appreviews/{appid}"
    reviews: list[dict] = []
    cursor = "*"
    page = 0

    while len(reviews) < num:
        params: dict[str, str | int] = {
            "json": 1,
            "language": language,
            "review_type": review_type,
            "purchase_type": "all",
            "num_per_page": min(100, num - len(reviews)),
            "cursor": cursor,
            "filter": "all",
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("Request failed (appid=%s, page=%d): %s", appid, page, e)
            break
        except json.JSONDecodeError as e:
            logger.warning("JSON decode error (appid=%s, page=%d): %s", appid, page, e)
            break

        if data.get("success") != 1:
            logger.warning("API returned success!=1 for appid=%s", appid)
            break

        batch = data.get("reviews", [])
        if not batch:
            logger.debug("No more reviews (appid=%s, lang=%s, page=%d)", appid, language, page)
            break

        reviews.extend(batch)
        page += 1

        new_cursor = data.get("cursor", "")
        if not new_cursor or new_cursor == cursor:
            break
        cursor = new_cursor

        time.sleep(sleep_sec)

    return reviews[:num]


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


def fetch_and_save(
    title: str,
    appid: int,
    language: str,
    review_type: ReviewType,
    num: int,
    overwrite: bool = False,
) -> Path:
    """
    レビューを取得してJSONファイルに保存する。

    Returns
    -------
    Path : 保存先パス（既存ファイルをスキップした場合も返す）
    """
    slug = _make_slug(title)
    out_path = RAW_DIR / f"{slug}_{language}_{review_type}.json"

    if out_path.exists() and not overwrite:
        logger.info("SKIP (exists): %s", out_path.name)
        return out_path

    logger.info(
        "Fetching %-30s | %-10s | %-8s | target=%d",
        title, language, review_type, num,
    )
    reviews = get_reviews(appid, language, review_type, num)
    logger.info("  → got %d reviews", len(reviews))

    payload = {
        "meta": {
            "title": title,
            "appid": appid,
            "language": language,
            "review_type": review_type,
            "fetched_count": len(reviews),
        },
        "reviews": reviews,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


# ─── 実行設定 ────────────────────────────────────────────────────────────────


def run_collection(
    game_list: list[tuple[str, int]] | None = None,
    languages: list[str] | None = None,
    neg_count: int = 300,
    pos_count: int = 300,
    overwrite: bool = False,
) -> list[Path]:
    """
    指定ゲーム × 言語 × レビュー種別 の全組み合わせでデータ取得を実行する。

    Parameters
    ----------
    game_list  : [(タイトル, appid), ...] 省略時は CORE_GAMES（設計書の5タイトル）
    languages  : 言語コードリスト。省略時は LANGUAGES（6言語）
    neg_count  : ネガティブレビュー取得目標数
    pos_count  : ポジティブレビュー取得目標数
    overwrite  : True なら既存ファイルを上書き

    Returns
    -------
    list[Path] : 保存したファイルのパスリスト
    """
    if game_list is None:
        game_list = list(CORE_GAMES.items())
    if languages is None:
        languages = LANGUAGES

    total_combinations = len(game_list) * len(languages) * 2
    logger.info(
        "=== Collection start: %d games × %d languages × 2 types = %d requests ===",
        len(game_list), len(languages), total_combinations,
    )

    saved: list[Path] = []
    done = 0

    for title, appid in game_list:
        for lang in languages:
            for review_type, count in [("negative", neg_count), ("positive", pos_count)]:
                path = fetch_and_save(title, appid, lang, review_type, count, overwrite)
                saved.append(path)
                done += 1
                logger.info("[%d/%d] done", done, total_combinations)

    logger.info("=== Collection complete: %d files saved to %s ===", len(saved), RAW_DIR)
    return saved


# ─── 取得済みデータの確認ユーティリティ ──────────────────────────────────────


def summarize_raw() -> None:
    """data/raw/ の取得済みファイルを一覧表示する。"""
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        print("No files in data/raw/")
        return

    total_reviews = 0
    print(f"\n{'File':<60} {'Count':>6}")
    print("-" * 68)
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            count = data["meta"]["fetched_count"]
            total_reviews += count
            print(f"{f.name:<60} {count:>6}")
        except Exception:
            print(f"{f.name:<60}  ERROR")
    print("-" * 68)
    print(f"{'TOTAL':<60} {total_reviews:>6}")
    print(f"\nFiles: {len(files)}  |  Reviews: {total_reviews:,}")


def load_reviews(
    title: str,
    language: str,
    review_type: ReviewType = "negative",
) -> list[dict]:
    """保存済みJSONからレビューをロードする。"""
    slug = _make_slug(title)
    path = RAW_DIR / f"{slug}_{language}_{review_type}.json"
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["reviews"]


# ─── エントリポイント ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Steam review collector")
    parser.add_argument(
        "--mode",
        choices=["core", "full", "summary"],
        default="summary",
        help=(
            "core: 設計書の5タイトルのみ取得  "
            "full: 全~100タイトル取得  "
            "summary: 取得済みファイルの確認"
        ),
    )
    parser.add_argument("--neg", type=int, default=300, help="ネガティブレビュー取得数")
    parser.add_argument("--pos", type=int, default=300, help="ポジティブレビュー取得数")
    parser.add_argument("--overwrite", action="store_true", help="既存ファイルを上書き")
    args = parser.parse_args()

    if args.mode == "summary":
        summarize_raw()
    elif args.mode == "core":
        run_collection(
            game_list=list(CORE_GAMES.items()),
            neg_count=args.neg,
            pos_count=args.pos,
            overwrite=args.overwrite,
        )
    elif args.mode == "full":
        game_list = [(title, appid) for title, appid, *_ in GAMES]
        run_collection(
            game_list=game_list,
            neg_count=args.neg,
            pos_count=args.pos,
            overwrite=args.overwrite,
        )
