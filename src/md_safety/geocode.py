"""Add coordinates to stations with the US Census Bureau batch geocoder.

Results are cached in ``data/geocoded/cache.csv`` so a refresh only geocodes
addresses it has not seen before. ``data/overrides.csv`` holds hand-fixed
coordinates, and those always win.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

import httpx

from md_safety.models import Station

log = logging.getLogger(__name__)

CENSUS_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
CENSUS_BENCHMARK = "Public_AR_Current"
CENSUS_TIMEOUT_SECONDS = 600.0  # a batch of 1,500 addresses can take a few minutes

# Maryland with a little margin, as (south, west, north, east).
MD_BOUNDS = (37.85, -79.55, 39.80, -74.95)

Coordinates = tuple[float, float]  # (lat, lon)


def address_key(station: Station) -> str:
    """Cache key: the address parts upper-cased, so re-casing never misses the cache."""
    raw = f"{station.address}|{station.city}|{station.state}|{station.zip}"
    return " ".join(raw.upper().split())


def in_maryland(lat: float, lon: float) -> bool:
    south, west, north, east = MD_BOUNDS
    return south <= lat <= north and west <= lon <= east


def read_cache(path: Path) -> dict[str, Coordinates]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            row["key"]: (float(row["lat"]), float(row["lon"])) for row in csv.DictReader(handle)
        }


def write_cache(path: Path, cache: dict[str, Coordinates]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("key", "lat", "lon"))
        for key in sorted(cache):
            lat, lon = cache[key]
            writer.writerow((key, f"{lat:.6f}", f"{lon:.6f}"))


def read_overrides(path: Path) -> dict[int, Coordinates]:
    """``data/overrides.csv``: columns ``id, lat, lon, note``."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            int(row["id"]): (float(row["lat"]), float(row["lon"])) for row in csv.DictReader(handle)
        }


def read_zip_centres(path: Path | None) -> dict[str, Coordinates]:
    """``data/md_zips.csv``: ZIP code centres from the Census ZCTA gazetteer."""
    if path is None or not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            row["zip"]: (float(row["lat"]), float(row["lon"])) for row in csv.DictReader(handle)
        }


def census_batch_csv(stations: Iterable[Station]) -> str:
    """The input the Census batch geocoder expects: id, street, city, state, zip, no header."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for station in stations:
        writer.writerow((station.id, station.address, station.city, station.state, station.zip))
    return buffer.getvalue()


def parse_census_results(text: str) -> dict[int, Coordinates]:
    """Coordinates by station id for the rows the geocoder matched.

    Matched rows look like ``id, input, Match, Exact, matched address, "lon,lat", tiger id,
    side``. Unmatched rows are just ``id, input, No_Match`` or ``id, input, Tie``.
    """
    found: dict[int, Coordinates] = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 6 and row[2] == "Match":
            lon, lat = (float(part) for part in row[5].split(","))
            found[int(row[0])] = (lat, lon)
    return found


def census_geocode(client: httpx.Client, stations: list[Station]) -> dict[int, Coordinates]:
    """One request to the Census batch geocoder, which accepts up to 10,000 addresses."""
    if not stations:
        return {}
    response = client.post(
        CENSUS_BATCH_URL,
        data={"benchmark": CENSUS_BENCHMARK},
        files={"addressFile": ("addresses.csv", census_batch_csv(stations).encode(), "text/csv")},
    )
    response.raise_for_status()
    return parse_census_results(response.text)


def geocode_stations(
    stations: list[Station],
    *,
    cache_path: Path,
    overrides_path: Path,
    zips_path: Path | None = None,
    client: httpx.Client | None = None,
) -> list[Station]:
    """Fill in coordinates from overrides, then the cache, then the Census geocoder.

    Stations the geocoder cannot place fall back to the centre of their ZIP code,
    marked ``geocode_source="zip"`` so the site can call them approximate. With
    ``client=None`` nothing touches the network. Points outside Maryland are misses.
    """
    cache = read_cache(cache_path)
    overrides = read_overrides(overrides_path)
    zips = read_zip_centres(zips_path)

    missing = [s for s in stations if address_key(s) not in cache and s.id not in overrides]
    if missing and client is not None:
        log.info("geocoding %d addresses with the Census Bureau", len(missing))
        results = census_geocode(client, missing)
        for station in missing:
            if station.id in results and in_maryland(*results[station.id]):
                cache[address_key(station)] = results[station.id]
        write_cache(cache_path, cache)

    located: list[Station] = []
    for station in stations:
        if station.id in overrides:
            lat, lon = overrides[station.id]
            located.append(replace(station, lat=lat, lon=lon, geocode_source="override"))
        elif address_key(station) in cache:
            lat, lon = cache[address_key(station)]
            located.append(replace(station, lat=lat, lon=lon, geocode_source="census"))
        elif station.zip in zips:
            lat, lon = zips[station.zip]
            located.append(replace(station, lat=lat, lon=lon, geocode_source="zip"))
        else:
            located.append(station)

    approximate = sum(1 for s in located if s.geocode_source == "zip")
    if approximate:
        log.info("%d stations placed at their ZIP centre (approximate)", approximate)

    unmatched = [s.id for s in located if s.lat is None]
    if unmatched:
        log.warning(
            "%d stations have no coordinates; fix them in %s", len(unmatched), overrides_path
        )
    return located
