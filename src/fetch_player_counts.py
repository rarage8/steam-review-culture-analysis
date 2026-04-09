from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from games_list import GAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
PLAYER_COUNTS_DIR = ROOT / "data" / "player_counts"
PLAYER_COUNTS_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_PATH = PLAYER_COUNTS_DIR / "current_players.csv"

CURRENT_PLAYERS_API = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"


def fetch_current_players(appid: int) -> int | None:
    try:
        response = requests.get(CURRENT_PLAYERS_API, params={"appid": appid}, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.warning("Failed to fetch current players for %s: %s", appid, exc)
        return None

    player_count = payload.get("response", {}).get("player_count")
    if player_count is None:
        return None
    return int(player_count)


def collect_player_snapshots(
    game_list: list[tuple[str, int]] | None = None,
    sleep_sec: float = 0.2,
) -> Path:
    if game_list is None:
        game_list = [(title, appid) for title, appid, *_ in GAMES]

    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, object]] = []

    for title, appid in game_list:
        player_count = fetch_current_players(appid)
        if player_count is None:
            continue
        rows.append(
            {
                "collected_at": now,
                "appid": appid,
                "title": title,
                "current_players": player_count,
            }
        )
        logger.info("%s | appid=%s | current_players=%s", title, appid, player_count)
        time.sleep(sleep_sec)

    new_df = pd.DataFrame(rows)
    if SNAPSHOT_PATH.exists():
        old_df = pd.read_csv(SNAPSHOT_PATH, encoding="utf-8")
        out_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        out_df = new_df

    out_df.to_csv(SNAPSHOT_PATH, index=False, encoding="utf-8")
    logger.info("Saved %d player-count snapshots to %s", len(new_df), SNAPSHOT_PATH)
    return SNAPSHOT_PATH


if __name__ == "__main__":
    collect_player_snapshots()
