"""Fetch the public station list from the Maryland State Police MSIS lookup.

Decision 0002 (``docs/decisions/0002-data-access.md``) sets the rules this module
enforces: small pages, a pause between requests, backoff on errors, a User-Agent
that says who we are, and a committed snapshot so nothing else in the project
ever needs the live site.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from md_safety import __version__

log = logging.getLogger(__name__)

API_URL = "https://egov.maryland.gov/msp/msis/api/Stations/PublicStationSearch"
SOURCE_PAGE = "https://egov.maryland.gov/msp/msis/lookup/stations"
REPO_URL = "https://github.com/xevanchan/md-safety"
USER_AGENT = f"md-safety/{__version__} (+{REPO_URL})"

DEFAULT_PAGE_SIZE = 2000  # one request covers every station; verified 2026-11-23 (1,520 rows)
DEFAULT_DELAY_SECONDS = 1.0
MAX_CONSECUTIVE_FAILURES = 3
TIMEOUT_SECONDS = 30.0

# Column names the lookup page sends; the first one is the sort key.
COLUMNS = ("stationNumber", "tradingName", "address", "phone", "types", "eInspections")


class FetchError(RuntimeError):
    """The MSIS endpoint could not be read, or answered with an unexpected shape."""


def build_payload(start: int, length: int, draw: int = 1) -> dict[str, Any]:
    """Build the DataTables request body the lookup page sends, with empty filters."""
    columns = [
        {
            "data": name,
            "name": "",
            "searchable": True,
            "orderable": name in {"stationNumber", "tradingName", "eInspections"},
            "search": {"value": "", "regex": False},
        }
        for name in COLUMNS
    ]
    return {
        "draw": draw,
        "start": start,
        "length": length,
        "order": [{"column": 0, "dir": "asc"}],
        "columns": columns,
        "search": {"value": "", "regex": False},
        # Filters from the page's form. Empty means every station.
        "stationName": "",
        "county": "",
        "city": "",
        "zip": None,
        "types": [],
    }


def new_client(
    transport: httpx.BaseTransport | None = None, timeout: float = TIMEOUT_SECONDS
) -> httpx.Client:
    """An HTTP client that identifies this project. ``transport`` lets tests fake the server."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        transport=transport,
    )


def fetch_page(client: httpx.Client, start: int, length: int, draw: int) -> tuple[list[dict], int]:
    response = client.post(API_URL, json=build_payload(start, length, draw))
    response.raise_for_status()
    body = response.json()
    data = body.get("data") if isinstance(body, dict) else None
    total = body.get("recordsFiltered") if isinstance(body, dict) else None
    if not isinstance(data, list) or not isinstance(total, int):
        raise FetchError("unexpected response shape from MSIS")
    return data, total


def fetch_all(
    client: httpx.Client,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    delay: float = DEFAULT_DELAY_SECONDS,
    max_failures: int = MAX_CONSECUTIVE_FAILURES,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Page through every station, pausing ``delay`` seconds between pages.

    A failed request is retried after an exponential backoff; ``max_failures``
    consecutive failures abort the run. If the server returns fewer rows than
    asked for, paging continues from where the server stopped, so asking for a
    large page is safe.
    """
    records: list[dict] = []
    start = 0
    draw = 1
    failures = 0
    total: int | None = None
    while True:
        try:
            page, total = fetch_page(client, start, page_size, draw)
        except (httpx.HTTPError, FetchError, ValueError) as exc:
            failures += 1
            if failures >= max_failures:
                raise FetchError(
                    f"giving up after {failures} consecutive failures at start={start}: {exc}"
                ) from exc
            wait = delay * 2**failures
            log.warning("request failed (%s); retrying in %.0fs", exc, wait)
            sleep(wait)
            continue
        failures = 0
        draw += 1
        records.extend(page)
        log.info("fetched %d of %d stations", len(records), total)
        if not page or len(records) >= total:
            break
        start += len(page)
        sleep(delay)
    if total is not None and len(records) != total:
        log.warning("server reported %d stations but returned %d", total, len(records))
    return records


def save_snapshot(records: list[dict], data_dir: Path, fetched_at: datetime | None = None) -> Path:
    """Write ``data/raw/latest.json`` and a dated copy. Returns the path of ``latest.json``."""
    fetched_at = fetched_at or datetime.now(UTC)
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "source": API_URL,
        "count": len(records),
        "records": records,
    }
    text = json.dumps(envelope, indent=1, ensure_ascii=False) + "\n"
    dated = raw_dir / f"stations-{fetched_at:%Y-%m-%d}.json"
    latest = raw_dir / "latest.json"
    for path in (dated, latest):
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return latest


def load_snapshot(path: Path) -> dict[str, Any]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("records"), list):
        raise ValueError(f"{path} is not a station snapshot")
    return snapshot


def fetch_stations(
    data_dir: Path,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    delay: float = DEFAULT_DELAY_SECONDS,
) -> Path:
    """Pull the full list from the live site and save a snapshot. Deliberate and rare."""
    log.info("fetching %s as %s", API_URL, USER_AGENT)
    with new_client() as client:
        records = fetch_all(client, page_size=page_size, delay=delay)
    return save_snapshot(records, data_dir)
