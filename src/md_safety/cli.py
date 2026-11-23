"""Command-line entry point for md-safety."""

from __future__ import annotations

import argparse

from md_safety import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="md-safety", description="TODO: describe md-safety.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code."""
    parser = build_parser()
    parser.parse_args(argv)
    print("md-safety is set up. Replace this message in src/md_safety/cli.py.")
    return 0
