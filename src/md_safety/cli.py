"""Command-line entry point for md-safety."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from md_safety import __version__
from md_safety.fetch import (
    DEFAULT_DELAY_SECONDS,
    DEFAULT_PAGE_SIZE,
    FetchError,
    fetch_stations,
    load_snapshot,
)
from md_safety.normalize import normalize_all, write_stations

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
    handlers = {"fetch": _fetch, "normalize": _normalize}
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
