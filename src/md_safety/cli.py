"""Command-line entry point for md-safety."""

from __future__ import annotations

import argparse
import logging
from contextlib import nullcontext
from pathlib import Path

from md_safety import __version__
from md_safety.build import BuildError, build_payload, check, previous_count, write_payload
from md_safety.fetch import (
    DEFAULT_DELAY_SECONDS,
    DEFAULT_PAGE_SIZE,
    FetchError,
    fetch_stations,
    load_snapshot,
    new_client,
)
from md_safety.geocode import CENSUS_TIMEOUT_SECONDS, geocode_stations
from md_safety.normalize import normalize_all, read_stations, write_stations

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-safety", description="Maryland inspection station finder: data pipeline commands."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    commands = parser.add_subparsers(dest="command", metavar="command")

    fetch = commands.add_parser(
        "fetch",
        help="pull the station list from the live MSIS lookup into data/raw/ (rare; decision 0002)",
    )
    fetch.add_argument("--data-dir", type=Path, default=Path("data"), help="folder holding raw/")
    fetch.add_argument(
        "--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="records per request"
    )
    fetch.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="seconds between requests"
    )

    normalize = commands.add_parser(
        "normalize", help="clean the raw snapshot into data/normalized/stations.json"
    )
    normalize.add_argument("--input", type=Path, default=Path("data/raw/latest.json"))
    normalize.add_argument("--output", type=Path, default=Path("data/normalized/stations.json"))

    geocode = commands.add_parser(
        "geocode", help="add coordinates from overrides, the cache, then the Census geocoder"
    )
    geocode.add_argument("--input", type=Path, default=Path("data/normalized/stations.json"))
    geocode.add_argument("--output", type=Path, default=Path("data/geocoded/stations.json"))
    geocode.add_argument("--cache", type=Path, default=Path("data/geocoded/cache.csv"))
    geocode.add_argument("--overrides", type=Path, default=Path("data/overrides.csv"))
    geocode.add_argument(
        "--zips",
        type=Path,
        default=Path("data/md_zips.csv"),
        help="ZIP centres used for stations the geocoder cannot place",
    )
    geocode.add_argument(
        "--offline", action="store_true", help="use only the cache and overrides, no network"
    )

    build = commands.add_parser(
        "build", help="write web/data/stations.json for the site, after sanity checks"
    )
    build.add_argument("--input", type=Path, default=Path("data/geocoded/stations.json"))
    build.add_argument("--snapshot", type=Path, default=Path("data/raw/latest.json"))
    build.add_argument("--output", type=Path, default=Path("web/data/stations.json"))
    build.add_argument("--force", action="store_true", help="write even if the checks fail")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s"
    )
    if args.command is None:
        parser.print_help()
        return 0
    handlers = {"fetch": _fetch, "normalize": _normalize, "geocode": _geocode, "build": _build}
    return handlers[args.command](args)


def _fetch(args: argparse.Namespace) -> int:
    try:
        latest = fetch_stations(args.data_dir, page_size=args.page_size, delay=args.delay)
    except FetchError as exc:
        log.error("fetch failed: %s", exc)
        return 1
    snapshot = load_snapshot(latest)
    print(f"saved {snapshot['count']} stations to {latest}")
    return 0


def _normalize(args: argparse.Namespace) -> int:
    if not args.input.exists():
        log.error("no snapshot at %s; run `md-safety fetch` first", args.input)
        return 1
    stations = normalize_all(load_snapshot(args.input)["records"])
    write_stations(stations, args.output)
    print(f"wrote {len(stations)} stations to {args.output}")
    return 0


def _geocode(args: argparse.Namespace) -> int:
    if not args.input.exists():
        log.error("no stations at %s; run `md-safety normalize` first", args.input)
        return 1
    stations = read_stations(args.input)
    with nullcontext() if args.offline else new_client(timeout=CENSUS_TIMEOUT_SECONDS) as client:
        located = geocode_stations(
            stations,
            cache_path=args.cache,
            overrides_path=args.overrides,
            zips_path=args.zips,
            client=client,
        )
    write_stations(located, args.output)
    with_coords = sum(1 for s in located if s.lat is not None)
    print(f"wrote {len(located)} stations ({with_coords} with coordinates) to {args.output}")
    return 0


def _build(args: argparse.Namespace) -> int:
    if not args.input.exists():
        log.error("no stations at %s; run `md-safety geocode` first", args.input)
        return 1
    stations = read_stations(args.input)
    fetched_at = load_snapshot(args.snapshot)["fetched_at"] if args.snapshot.exists() else None
    try:
        check(stations, previous_count(args.output))
    except BuildError as exc:
        if not args.force:
            log.error("refusing to build: %s (use --force to override)", exc)
            return 1
        log.warning("building anyway: %s", exc)
    payload = build_payload(stations, fetched_at=fetched_at)
    write_payload(payload, args.output)
    print(f"wrote {payload['count']} stations ({payload['located']} located) to {args.output}")
    return 0
