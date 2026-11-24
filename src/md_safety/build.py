"""Assemble the JSON the website loads, after two sanity checks."""

from __future__ import annotations

import csv
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from md_safety.fetch import SOURCE_PAGE
from md_safety.models import Station

log = logging.getLogger(__name__)

MAX_UNMATCHED_SHARE = 0.02  # refuse if more than 2% of stations have no coordinates
MAX_COUNT_CHANGE = 0.10  # refuse if the station count moved more than 10% since last build


class BuildError(RuntimeError):
    """The data looks wrong; do not overwrite the site's copy."""


def check(stations: list[Station], previous_count: int | None) -> None:
    unmatched = sum(1 for s in stations if s.lat is None)
    if stations and unmatched / len(stations) > MAX_UNMATCHED_SHARE:
        raise BuildError(f"{unmatched} of {len(stations)} stations have no coordinates")
    if previous_count and abs(len(stations) - previous_count) / previous_count > MAX_COUNT_CHANGE:
        raise BuildError(f"station count went from {previous_count} to {len(stations)}")


def site_record(station: Station) -> dict:
    """The fields the site needs, and nothing else."""
    return {
        "id": station.id,
        "name": station.name,
        "address": station.address,
        "city": station.city,
        "zip": station.zip,
        "phone": station.phone,
        "classes": list(station.classes),
        "e_inspection": station.e_inspection,
        "lat": None if station.lat is None else round(station.lat, 5),
        "lon": None if station.lon is None else round(station.lon, 5),
        "approx": station.geocode_source == "zip",
    }


def build_payload(
    stations: list[Station], *, fetched_at: str | None, generated_at: datetime | None = None
) -> dict:
    generated_at = generated_at or datetime.now(UTC)
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "source_url": SOURCE_PAGE,
        "fetched_at": fetched_at,
        "count": len(stations),
        "located": sum(1 for s in stations if s.lat is not None),
        "stations": [site_record(s) for s in stations],
    }


def previous_count(path: Path) -> int | None:
    """Station count from the last build, or ``None`` when there is none."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("count")


def write_payload(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")


def write_zips(zips_csv: Path, path: Path) -> int:
    """``web/data/zips.json``: ZIP code to ``[lat, lon]``, for the site's ZIP search."""
    with zips_csv.open(encoding="utf-8", newline="") as handle:
        zips = {
            row["zip"]: [float(row["lat"]), float(row["lon"])] for row in csv.DictReader(handle)
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(zips, separators=(",", ":")) + "\n")
    return len(zips)
