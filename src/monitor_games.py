"""
monitor_games.py: Steam 新着・人気ゲームの自動検出スクリプト
─────────────────────────────────────────────────────────────
SteamSpy API (無料) を使い、直近のトップ人気ゲームを取得して
games_list.py に未登録のタイトルを検出する。

使い方:
  cd src
  python monitor_games.py               # 上位500タイトルを検索
  python monitor_games.py --top 1000    # 上位1000タイトル
  python monitor_games.py --min-pos 5000  # 最低ポジティブ数を設定
  python monitor_games.py --auto-add   # games_list.py に自動追記

GitHub Actions からも呼び出される（.github/workflows/auto_collect.yml 参照）。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── 定数 ─────────────────────────────────────────────────────────────────────

STEAMSPY_API    = "https://steamspy.com/api.php"
STEAM_DETAILS   = "https://store.steampowered.com/api/appdetails"

DEFAULT_TOP          = 500
DEFAULT_MIN_POSITIVE = 2000   # 最低ポジティブレビュー数
MAX_NEW_PER_RUN      = 10     # 1回の実行で追加するゲームの上限

# ─── SteamSpy ─────────────────────────────────────────────────────────────────


def _fetch_steamspy_page(page: int) -> dict:
    """SteamSpy の全ゲームリスト (1ページ = 1000件) を取得する。"""
    params = {"request": "all", "page": page}
    resp = requests.get(STEAMSPY_API, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_top_games(top_n: int = DEFAULT_TOP) -> list[dict]:
    """
    SteamSpy から人気ゲームを取得する。

    Returns
    -------
    list[dict] : {"appid", "name", "positive", "negative", "owners", ...}
    """
    games: list[dict] = []
    page = 0
    while len(games) < top_n:
        logger.info("Fetching SteamSpy page %d (collected %d)...", page, len(games))
        try:
            batch = _fetch_steamspy_page(page)
        except requests.RequestException as e:
            logger.warning("SteamSpy page %d failed: %s", page, e)
            break

        if not batch:
            break

        games.extend(batch.values())
        page += 1
        time.sleep(1.5)  # SteamSpy rate limit

    logger.info("Fetched %d games from SteamSpy", len(games))
    return games[:top_n]


# ─── 既存ゲームリストの読み込み ───────────────────────────────────────────────


def load_existing_appids() -> set[int]:
    """games_list.py の GAMES から既存 appid を読み込む。"""
    src_dir = Path(__file__).parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from games_list import GAMES  # type: ignore
    return {int(appid) for _, appid, *_ in GAMES}


def load_existing_titles() -> set[str]:
    """games_list.py の GAMES から既存タイトルを読み込む（小文字）。"""
    src_dir = Path(__file__).parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from games_list import GAMES  # type: ignore
    return {title.lower() for title, *_ in GAMES}


# ─── ゲームジャンル・地域の推定 ───────────────────────────────────────────────


def _guess_genre(tags: list[str]) -> str:
    """SteamSpy のタグからジャンルを推定する（簡易版）。"""
    tag_lower = {t.lower() for t in tags}
    priority = [
        ("RPG",          {"rpg", "jrpg", "action rpg", "turn-based rpg"}),
        ("FPS",          {"fps", "first-person shooter"}),
        ("Strategy",     {"strategy", "turn-based strategy", "grand strategy", "rts"}),
        ("Puzzle",       {"puzzle"}),
        ("Simulation",   {"simulation", "farming sim", "life sim", "management"}),
        ("Sports",       {"sports", "football", "racing", "soccer"}),
        ("Action",       {"action", "beat 'em up", "hack and slash"}),
        ("Adventure",    {"adventure", "point & click", "visual novel"}),
        ("Sandbox",      {"sandbox", "open world", "survival"}),
        ("Horror",       {"horror", "survival horror"}),
        ("Fighting",     {"fighting"}),
        ("Platformer",   {"platformer", "2d platformer"}),
        ("Other",        set()),
    ]
    for genre, keywords in priority:
        if tag_lower & keywords:
            return genre
    return "Other"


def _guess_dev_region(developer: str) -> str:
    """開発者名から開発地域を大まかに推定する（簡易版）。"""
    dev = developer.lower()
    jp = {"fromsoft", "square", "capcom", "konami", "sega", "atlus", "marvelous",
          "arc system", "koei", "grasshopper", "level-5", "nintendo", "bandai namco"}
    kr = {"nexon", "ncsoft", "netmarble", "krafton", "smilegate", "com2us"}
    cn = {"mihoyo", "hoyoverse", "tencent", "netease", "perfect world", "lilith",
          "moonton", "mechafantasy", "papergames"}
    eu = {"cd projekt", "ubisoft", "paradox", "fatshark", "rebellion", "hello games",
          "frontier", "focus", "tripwire", "2k czech", "people can fly", "techland",
          "bohemia", "warhorse", "klei", "fatshark", "ice-pick"}
    if any(k in dev for k in jp):
        return "Japan"
    if any(k in dev for k in kr):
        return "Korea"
    if any(k in dev for k in cn):
        return "China"
    if any(k in dev for k in eu):
        return "Europe"
    return "Western"


# ─── 新規ゲームの検出 ─────────────────────────────────────────────────────────


def find_new_games(
    top_games: list[dict],
    existing_appids: set[int],
    min_positive: int = DEFAULT_MIN_POSITIVE,
    limit: int = MAX_NEW_PER_RUN,
) -> list[dict]:
    """
    既存リストに存在しない人気ゲームを返す。

    Returns
    -------
    list[dict] : SteamSpy の game dict（positive 降順ソート済み）
    """
    new_games = [
        g for g in top_games
        if int(g.get("appid", 0)) not in existing_appids
        and g.get("positive", 0) >= min_positive
        and g.get("name", "").strip()
    ]
    new_games.sort(key=lambda x: x.get("positive", 0), reverse=True)
    return new_games[:limit]


# ─── games_list.py への自動追記 ────────────────────────────────────────────────


def append_to_games_list(new_games: list[dict]) -> int:
    """
    games_list.py の GAMES リストに新ゲームを追記する。

    Returns
    -------
    int : 追加した件数
    """
    games_list_path = Path(__file__).parent / "games_list.py"
    content = games_list_path.read_text(encoding="utf-8")

    # GAMES リストの末尾 "]" を探して手前に追記
    insert_marker = "]  # END_GAMES"
    if insert_marker not in content:
        logger.warning("Cannot auto-append: END_GAMES marker not found in games_list.py")
        return 0

    lines: list[str] = []
    existing_titles = load_existing_titles()
    added = 0

    for g in new_games:
        title = g.get("name", "").strip()
        appid = int(g.get("appid", 0))
        tags  = g.get("tags", {})
        tag_list = list(tags.keys()) if isinstance(tags, dict) else []
        developer = g.get("developer", "")

        if title.lower() in existing_titles:
            continue

        genre  = _guess_genre(tag_list)
        region = _guess_dev_region(developer)
        # Python の文字列エスケープ
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    ("{safe_title}", {appid}, "{genre}", "{region}"),  # auto-detected')
        existing_titles.add(title.lower())
        added += 1

    if not lines:
        logger.info("No new games to add (all already exist or no valid entries)")
        return 0

    new_entries = "\n".join(lines) + "\n"
    content = content.replace(insert_marker, new_entries + insert_marker)
    games_list_path.write_text(content, encoding="utf-8")
    logger.info("Appended %d new games to games_list.py", added)
    return added


# ─── エントリポイント ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Steam 新着・人気ゲームの検出")
    parser.add_argument("--top",      type=int, default=DEFAULT_TOP,
                        help=f"SteamSpy から取得するゲーム数 (default: {DEFAULT_TOP})")
    parser.add_argument("--min-pos",  type=int, default=DEFAULT_MIN_POSITIVE,
                        help=f"最低ポジティブレビュー数 (default: {DEFAULT_MIN_POSITIVE})")
    parser.add_argument("--limit",    type=int, default=MAX_NEW_PER_RUN,
                        help=f"検出する新規ゲームの上限 (default: {MAX_NEW_PER_RUN})")
    parser.add_argument("--auto-add", action="store_true",
                        help="games_list.py に新ゲームを自動追記する")
    parser.add_argument("--output",   type=str, default="new_games_detected.json",
                        help="検出結果の出力JSONファイル (default: new_games_detected.json)")
    args = parser.parse_args()

    # 1. SteamSpy からトップゲームを取得
    top_games = fetch_top_games(args.top)

    # 2. 既存リストとの差分を検出
    existing_appids = load_existing_appids()
    new_games = find_new_games(top_games, existing_appids, args.min_pos, args.limit)

    # 3. 結果を表示
    print(f"\n=== {len(new_games)} new popular games detected ===")
    print(f"{'Title':<55} {'AppID':>8}  {'Positive':>10}")
    print("-" * 78)
    for g in new_games:
        print(f"{g['name']:<55} {g['appid']:>8}  {g.get('positive', 0):>10,}")

    # 4. JSON 出力（GitHub Actions から参照）
    output_data = [
        {
            "title":    g["name"],
            "appid":    int(g["appid"]),
            "positive": g.get("positive", 0),
            "negative": g.get("negative", 0),
        }
        for g in new_games
    ]
    out_path = Path(args.output)
    out_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to {out_path}")

    # 5. 自動追記
    if args.auto_add and new_games:
        added = append_to_games_list(new_games)
        print(f"Added {added} games to games_list.py")
