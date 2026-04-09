from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

from games_list import GAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
CLASSIFIED_DIR = ROOT / "data" / "classified"
PLAYER_COUNTS_DIR = ROOT / "data" / "player_counts"
WEB_DATA_DIR = ROOT / "web" / "data"
WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
PLAYER_COUNTS_DIR.mkdir(parents=True, exist_ok=True)

LANGUAGES = ["japanese", "english", "schinese", "russian", "german", "koreana"]
REVIEW_TYPES = ["positive", "negative"]
SAMPLE_PER_SENTIMENT = 8
TRANSLATION_MODEL = "claude-sonnet-4-5"


@dataclass
class SourceRecord:
    appid: int
    title: str
    stem: str
    language: str
    review_type: str
    raw_path: Path


def make_slug(title: str) -> str:
    return (
        title.lower()
        .replace(" ", "_")
        .replace(":", "")
        .replace("'", "")
        .replace(".", "")
        .replace("-", "_")
        .replace("__", "_")
    )


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() == "true"


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _minutes_to_hours(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        return None
    if minutes <= 0:
        return None
    return round(minutes / 60.0, 2)


def _hours_to_days(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value / 24.0, 2)


def discover_sources() -> dict[tuple[int, str, str], SourceRecord]:
    sources: dict[tuple[int, str, str], SourceRecord] = {}
    for raw_path in sorted(RAW_DIR.glob("*.json")):
        try:
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover
            logger.warning("Skipping unreadable raw file %s: %s", raw_path.name, exc)
            continue

        meta = payload.get("meta", {})
        appid = int(meta.get("appid", 0))
        language = str(meta.get("language", ""))
        review_type = str(meta.get("review_type", ""))
        title = str(meta.get("title", ""))
        if not appid or language not in LANGUAGES or review_type not in REVIEW_TYPES:
            continue

        sources[(appid, language, review_type)] = SourceRecord(
            appid=appid,
            title=title,
            stem=raw_path.stem,
            language=language,
            review_type=review_type,
            raw_path=raw_path,
        )
    return sources


def load_review_frame(record: SourceRecord) -> pd.DataFrame:
    classified_path = CLASSIFIED_DIR / f"{record.stem}_classified.csv"
    processed_path = PROCESSED_DIR / f"{record.stem}_translated.csv"

    if classified_path.exists():
        df = pd.read_csv(classified_path, encoding="utf-8")
    elif processed_path.exists():
        df = pd.read_csv(processed_path, encoding="utf-8")
    else:
        payload = json.loads(record.raw_path.read_text(encoding="utf-8"))
        rows = []
        for review in payload.get("reviews", []):
            author = review.get("author", {})
            rows.append(
                {
                    "game": payload["meta"].get("title", record.title),
                    "language": record.language,
                    "review_type": record.review_type,
                    "review_text_orig": review.get("review", ""),
                    "review_text_en": review.get("review", "") if record.language == "english" else "",
                    "voted_up": review.get("voted_up"),
                    "votes_up": review.get("votes_up", 0),
                    "playtime_forever": author.get("playtime_forever", 0),
                    "playtime_at_review": author.get("playtime_at_review", 0),
                    "timestamp_created": review.get("timestamp_created"),
                    "app_release_date": review.get("app_release_date"),
                }
            )
        df = pd.DataFrame(rows)

    if df.empty:
        return df

    for column, default in {
        "review_text_orig": "",
        "review_text_en": "",
        "sentiment": "",
        "votes_up": 0,
        "playtime_at_review": pd.NA,
        "playtime_forever": pd.NA,
    }.items():
        if column not in df.columns:
            df[column] = default

    df["voted_up"] = df["voted_up"].map(_normalize_bool)
    df["review_text_orig"] = df["review_text_orig"].map(_normalize_text)
    df["review_text_en"] = df["review_text_en"].map(_normalize_text)
    df["sentiment"] = df["sentiment"].fillna("").astype(str).str.strip().str.lower()
    df["votes_up"] = pd.to_numeric(df["votes_up"], errors="coerce").fillna(0)
    df["playtime_at_review_h"] = df["playtime_at_review"].map(_minutes_to_hours)
    df["playtime_forever_h"] = df["playtime_forever"].map(_minutes_to_hours)
    df["time_spent_before_review_h"] = df["playtime_at_review_h"].fillna(df["playtime_forever_h"])
    df["time_spent_before_review_d"] = df["time_spent_before_review_h"].map(_hours_to_days)
    return df


def partition_sentiments(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    has_explicit = df["sentiment"].isin({"positive", "neutral", "negative"}).any()
    if has_explicit:
        pos_df = df[df["sentiment"] == "positive"].copy()
        neu_df = df[df["sentiment"] == "neutral"].copy()
        neg_df = df[df["sentiment"] == "negative"].copy()
        unset_df = df[~df["sentiment"].isin({"positive", "neutral", "negative"})]
        pos_df = pd.concat([pos_df, unset_df[unset_df["voted_up"] == True]], ignore_index=True)
        neg_df = pd.concat([neg_df, unset_df[unset_df["voted_up"] == False]], ignore_index=True)
    else:
        pos_df = df[df["voted_up"] == True].copy()
        neg_df = df[df["voted_up"] == False].copy()
        neu_df = df.iloc[0:0].copy()
    return {"positive": pos_df, "neutral": neu_df, "negative": neg_df}


def build_translation_client() -> Any | None:
    if anthropic is None or not os.getenv("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic()


def load_translation_cache() -> dict[str, dict[str, str]]:
    cache_path = WEB_DATA_DIR / "review_translation_cache.json"
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_translation_cache(cache: dict[str, dict[str, str]]) -> None:
    cache_path = WEB_DATA_DIR / "review_translation_cache.json"
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def translate_batch(
    texts: list[str],
    source_language: str,
    target_language: str,
    client: Any | None,
) -> list[str]:
    if not texts:
        return []
    if source_language == target_language or client is None:
        return texts

    numbered = "\n\n".join(f"[{i + 1}] {text}" for i, text in enumerate(texts))
    prompt = (
        f"Translate the following Steam game reviews from {source_language} to {target_language}.\n"
        "Keep tone, slang, praise, sarcasm, and criticism intact.\n"
        "Return only a JSON array of translated strings in the same order.\n\n"
        f"{numbered}"
    )
    try:
        response = client.messages.create(
            model=TRANSLATION_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            translated = json.loads(raw[start : end + 1])
            if isinstance(translated, list) and len(translated) == len(texts):
                return [_normalize_text(text) for text in translated]
    except Exception as exc:  # pragma: no cover
        logger.warning("Translation fallback for %s -> %s: %s", source_language, target_language, exc)
    return texts


def translate_review_samples(
    review_rows: list[dict[str, str]],
    source_language: str,
    client: Any | None,
    cache: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    translated_reviews: list[dict[str, Any]] = []
    for row in review_rows:
        original = row["original"]
        english = row["english"] or original
        translations: dict[str, str] = {}
        for target in LANGUAGES:
            cache_key = json.dumps(
                {"src": source_language, "target": target, "text": english},
                ensure_ascii=False,
                sort_keys=True,
            )
            cached = cache.get(cache_key, {}).get("text")
            if cached:
                translations[target] = cached
                continue

            if target == source_language:
                translated = original
            elif target == "english":
                translated = english
            else:
                translated = translate_batch([english], "english", target, client)[0]
            if client is not None:
                cache[cache_key] = {"text": translated}
            translations[target] = translated

        translated_reviews.append(
            {
                "original": original,
                "english": english,
                "translations": translations,
            }
        )
    return translated_reviews


def summarize_timing(df: pd.DataFrame) -> dict[str, float | int | None]:
    series = pd.to_numeric(df["time_spent_before_review_d"], errors="coerce").dropna()
    if series.empty:
        return {
            "count": 0,
            "avg_days": None,
            "median_days": None,
            "p75_days": None,
            "avg_hours": None,
        }
    hours = pd.to_numeric(df["time_spent_before_review_h"], errors="coerce").dropna()
    return {
        "count": int(series.count()),
        "avg_days": round(float(series.mean()), 2),
        "median_days": round(float(series.median()), 2),
        "p75_days": round(float(series.quantile(0.75)), 2),
        "avg_hours": round(float(hours.mean()), 2) if not hours.empty else None,
    }


def sample_review_rows(df: pd.DataFrame, limit: int) -> list[dict[str, str]]:
    if df.empty:
        return []
    ranked = df.sort_values(["votes_up", "time_spent_before_review_h"], ascending=[False, False])
    rows: list[dict[str, str]] = []
    for _, row in ranked.iterrows():
        original = _normalize_text(row.get("review_text_orig"))
        english = _normalize_text(row.get("review_text_en"))
        if not original and not english:
            continue
        rows.append({"original": original or english, "english": english or original})
        if len(rows) >= limit:
            break
    return rows


def load_population_snapshots() -> pd.DataFrame:
    snapshot_path = PLAYER_COUNTS_DIR / "current_players.csv"
    if not snapshot_path.exists():
        return pd.DataFrame(columns=["collected_at", "appid", "current_players"])
    df = pd.read_csv(snapshot_path, encoding="utf-8")
    if df.empty:
        return df
    df["collected_at"] = pd.to_datetime(df["collected_at"], errors="coerce", utc=True)
    df["appid"] = pd.to_numeric(df["appid"], errors="coerce").astype("Int64")
    df["current_players"] = pd.to_numeric(df["current_players"], errors="coerce")
    return df.dropna(subset=["collected_at", "appid", "current_players"])


def aggregate_population(
    snapshots: pd.DataFrame,
    game_index: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    if snapshots.empty:
        return {"daily": [], "weekly": [], "monthly": [], "last_snapshot_at": None}

    df = snapshots.copy()
    df = df[df["appid"].isin(game_index)]
    if df.empty:
        return {"daily": [], "weekly": [], "monthly": [], "last_snapshot_at": None}

    period_specs = {
        "daily": ("D", "%Y-%m-%d"),
        "weekly": ("W-MON", "%Y-%m-%d"),
        "monthly": ("MS", "%Y-%m"),
    }
    result: dict[str, Any] = {
        "last_snapshot_at": df["collected_at"].max().isoformat(),
    }

    for key, (freq, fmt) in period_specs.items():
        bucketed = (
            df.assign(bucket=df["collected_at"].dt.to_period(freq).dt.to_timestamp())
            .groupby(["bucket", "appid"], as_index=False)["current_players"]
            .mean()
        )
        rows = []
        for bucket, group in bucketed.groupby("bucket"):
            values = {
                game_index[int(appid)]["id"]: int(round(value))
                for appid, value in zip(group["appid"], group["current_players"])
                if int(appid) in game_index
            }
            rows.append({"bucket": bucket.strftime(fmt), "values": values})
        result[key] = rows

    return result


def build_dashboard_data(
    game_list: list[tuple[str, int]] | None = None,
    sample_per_sentiment: int = SAMPLE_PER_SENTIMENT,
) -> dict[str, Any]:
    if game_list is None:
        game_list = [(title, appid) for title, appid, *_ in GAMES]

    game_meta_by_appid = {
        appid: {
            "id": make_slug(title),
            "title": title,
            "appid": appid,
            "genre": genre,
            "region": region,
        }
        for title, appid, genre, region in GAMES
    }
    for title, appid in game_list:
        game_meta_by_appid.setdefault(
            appid,
            {"id": make_slug(title), "title": title, "appid": appid, "genre": "unknown", "region": "unknown"},
        )

    sources = discover_sources()
    translation_client = build_translation_client()
    translation_cache = load_translation_cache() if translation_client is not None else {}

    games_meta: list[dict[str, Any]] = []
    reviews_data: dict[str, Any] = {}

    for appid, meta in game_meta_by_appid.items():
        game_languages = {}
        for language in LANGUAGES:
            frames = []
            for review_type in REVIEW_TYPES:
                record = sources.get((appid, language, review_type))
                if record is None:
                    continue
                frame = load_review_frame(record)
                if not frame.empty:
                    frames.append(frame)

            if not frames:
                continue

            df_all = pd.concat(frames, ignore_index=True)
            sentiment_frames = partition_sentiments(df_all)
            total = len(df_all)
            pos_count = len(sentiment_frames["positive"])
            neu_count = len(sentiment_frames["neutral"])
            neg_count = len(sentiment_frames["negative"])
            approval_rate = round(pos_count / total, 4) if total else 0.0

            samples = {
                sentiment: translate_review_samples(
                    sample_review_rows(frame, sample_per_sentiment),
                    source_language=language,
                    client=translation_client,
                    cache=translation_cache,
                )
                for sentiment, frame in sentiment_frames.items()
            }
            timing = {sentiment: summarize_timing(frame) for sentiment, frame in sentiment_frames.items()}

            avg_hours = timing["positive"]["avg_hours"]
            if avg_hours is None:
                merged_hours = pd.to_numeric(df_all["time_spent_before_review_h"], errors="coerce").dropna()
                avg_hours = round(float(merged_hours.mean()), 2) if not merged_hours.empty else None

            game_languages[language] = {
                "approval_rate": approval_rate,
                "total_count": total,
                "pos_count": pos_count,
                "neu_count": neu_count,
                "neg_count": neg_count,
                "avg_playtime_review_h": avg_hours,
                "review_timing": timing,
                "sample_reviews": samples,
            }
            logger.info(
                "%s | %s | pos=%d neu=%d neg=%d rate=%.2f",
                meta["title"],
                language,
                pos_count,
                neu_count,
                neg_count,
                approval_rate,
            )

        if not game_languages:
            continue

        games_meta.append({**meta, "languages": sorted(game_languages.keys())})
        reviews_data[meta["id"]] = game_languages

    if translation_client is not None:
        save_translation_cache(translation_cache)

    snapshots = load_population_snapshots()
    game_index = {game["appid"]: game for game in games_meta}
    population = aggregate_population(snapshots, game_index)

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ui_languages": LANGUAGES,
            "game_count": len(games_meta),
            "review_source": "classified>processed>raw",
            "timing_metric": "time_spent_before_review",
            "timing_metric_unit": "days",
            "population_source": "data/player_counts/current_players.csv",
        },
        "games": sorted(games_meta, key=lambda item: item["title"].lower()),
        "reviews": reviews_data,
        "population": population,
    }


def export_dashboard_data(
    game_list: list[tuple[str, int]] | None = None,
    sample_per_sentiment: int = SAMPLE_PER_SENTIMENT,
) -> Path:
    payload = build_dashboard_data(game_list=game_list, sample_per_sentiment=sample_per_sentiment)
    out_path = WEB_DATA_DIR / "games.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Exported dashboard data to %s", out_path)
    return out_path


if __name__ == "__main__":
    export_dashboard_data()
