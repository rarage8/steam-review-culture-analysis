from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from build_dashboard_data import export_dashboard_data
from fetch_player_counts import collect_player_snapshots
from fetch_reviews import run_collection
from translate import run_translation
from classify import run_classification
from monitor_games import (
    DEFAULT_MIN_POSITIVE,
    MAX_NEW_PER_RUN,
    append_to_games_list,
    fetch_top_games,
    find_new_games,
    load_existing_appids,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"


def current_review_games() -> list[tuple[str, int]]:
    game_map: dict[int, str] = {}
    for path in RAW_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = payload.get("meta", {})
        appid = int(meta.get("appid", 0) or 0)
        title = str(meta.get("title", "")).strip()
        if appid and title:
            game_map[appid] = title
    return sorted(((title, appid) for appid, title in game_map.items()), key=lambda item: item[0].lower())


def detect_and_optionally_add_new_games(
    top_n: int,
    min_positive: int,
    limit: int,
    auto_add: bool,
) -> list[tuple[str, int]]:
    top_games = fetch_top_games(top_n)
    existing_appids = load_existing_appids()
    new_games = find_new_games(top_games, existing_appids, min_positive=min_positive, limit=limit)

    output_path = ROOT / "new_games_detected.json"
    output_path.write_text(
        json.dumps(
            [
                {
                    "title": item["name"],
                    "appid": int(item["appid"]),
                    "positive": item.get("positive", 0),
                    "negative": item.get("negative", 0),
                }
                for item in new_games
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if auto_add and new_games:
        append_to_games_list(new_games)

    logger.info("Detected %d new games", len(new_games))
    return [(item["name"], int(item["appid"])) for item in new_games]


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh dashboard data and optional auto-discovery")
    parser.add_argument("--detect-new", action="store_true", help="Detect newly popular games before exporting")
    parser.add_argument("--auto-add", action="store_true", help="Append detected games to games_list.py")
    parser.add_argument("--top", type=int, default=500, help="SteamSpy ranking depth")
    parser.add_argument("--min-positive", type=int, default=DEFAULT_MIN_POSITIVE, help="Minimum positive reviews")
    parser.add_argument("--limit", type=int, default=MAX_NEW_PER_RUN, help="Maximum detected games per run")
    parser.add_argument("--skip-player-counts", action="store_true", help="Skip current-player snapshot collection")
    parser.add_argument("--skip-review-refresh", action="store_true", help="Skip refreshing review data")
    args = parser.parse_args()

    detected_games: list[tuple[str, int]] = []
    if args.detect_new:
        detected_games = detect_and_optionally_add_new_games(
            top_n=args.top,
            min_positive=args.min_positive,
            limit=args.limit,
            auto_add=args.auto_add,
        )

    if not args.skip_player_counts:
        collect_player_snapshots()

    if not args.skip_review_refresh:
        tracked_games = current_review_games()
        if tracked_games:
            run_collection(game_list=tracked_games, overwrite=True, neg_count=300, pos_count=300)
            run_translation(game_list=tracked_games, overwrite=True)
            run_classification(game_list=tracked_games, overwrite=True)

    export_dashboard_data()
    if detected_games:
        logger.info("New games in this refresh: %s", ", ".join(title for title, _ in detected_games))


if __name__ == "__main__":
    main()
