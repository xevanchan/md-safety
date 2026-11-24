"""Turn raw MSIS records into clean :class:`Station` objects.

The state's data is mostly UPPERCASE, with inconsistent phone formats and a
comma-separated class string. Everything here is a pure function, so the tests
run from fixtures alone.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from pathlib import Path

from md_safety.models import Station

log = logging.getLogger(__name__)

# Tokens that stay uppercase when an all-caps string is re-cased.
KEEP_UPPER = frozenset(
    {
        "LLC", "DBA", "USA", "US", "DC", "MD", "PO", "II", "III", "IV",
        "BMW", "GMC", "VW", "RV", "CDJR", "AAA", "MVA", "BP", "JBA", "IG",
        "N", "S", "E", "W", "NE", "NW", "SE", "SW",
    }
)  # fmt: skip

# Words that go lowercase unless they start the string.
SMALL_WORDS = frozenset({"of", "and", "the", "at", "in", "on", "for", "de", "du", "la", "le"})

# Vehicle classes in the order the site should list them. ``T`` appears in the
# data but not in the state's legend, which lists ``TL``; see the workplan.
CLASS_ORDER = ("A", "B", "C", "M", "TL", "T", "R", "F", "A/M Trailer")

STATE_CODES = {
    "maryland": "MD",
    "virginia": "VA",
    "pennsylvania": "PA",
    "delaware": "DE",
    "west virginia": "WV",
    "district of columbia": "DC",
}

_WORD = re.compile(r"^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$", re.DOTALL)


def smart_title(text: str) -> str:
    """Re-case an all-caps string for display.

    Strings that already contain lowercase letters were typed by a human and
    come back unchanged apart from collapsed whitespace.
    """
    words = text.split()
    if not words or any(ch.islower() for ch in text):
        return " ".join(words)
    return " ".join(_case_word(word, first=index == 0) for index, word in enumerate(words))


def _case_word(word: str, *, first: bool) -> str:
    match = _WORD.match(word)
    assert match is not None  # the pattern matches any string
    leading, core, trailing = match.groups()
    if core in KEEP_UPPER:
        return word
    if not first and core.lower() in SMALL_WORDS:
        return leading + core.lower() + trailing
    parts = re.split(r"([-/])", core)
    return leading + "".join(_case_part(part) for part in parts) + trailing


def _case_part(part: str) -> str:
    if not part or part in "-/" or part in KEEP_UPPER:
        return part
    if part[0].isdigit():
        return part.lower()  # 21ST -> 21st; the A in 427-A is its own part
    if len(part) > 2 and part[1] == "'":
        return part[0] + "'" + part[2].upper() + part[3:].lower()  # O'BRIEN -> O'Brien
    if part.startswith("MC") and len(part) > 3:
        return "Mc" + part[2] + part[3:].lower()  # MCCARTHY -> McCarthy
    return part[0] + part[1:].lower()


def format_phone(raw: str | None) -> str | None:
    """Return ``(xxx) xxx-xxxx`` when the digits allow it, the trimmed input otherwise."""
    text = (raw or "").strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return text
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def split_classes(types: str | None) -> tuple[str, ...]:
    """Split the state's comma string into unique class codes in display order."""
    seen: list[str] = []
    for part in (types or "").split(","):
        code = part.strip()
        if code and code not in seen:
            seen.append(code)
    return tuple(sorted(seen, key=_class_rank))


def _class_rank(code: str) -> int:
    return CLASS_ORDER.index(code) if code in CLASS_ORDER else len(CLASS_ORDER)


def state_code(raw: str | None) -> str:
    text = (raw or "").strip()
    if len(text) == 2:
        return text.upper()
    return STATE_CODES.get(text.lower(), text)


def clean_zip(raw: str | None) -> str:
    text = (raw or "").strip()
    match = re.match(r"\d{5}", text)
    return match.group(0) if match else text


def normalize_record(raw: dict) -> Station:
    name = str(raw.get("tradingName") or "").strip()
    address = str(raw.get("address") or "").strip()
    return Station(
        id=int(raw["stationNumber"]),
        name=smart_title(name),
        address=smart_title(address),
        city=smart_title(str(raw.get("city") or "")),
        state=state_code(raw.get("state")),
        zip=clean_zip(raw.get("zipCode")),
        phone=format_phone(raw.get("phone")),
        classes=split_classes(raw.get("types")),
        e_inspection=bool(raw.get("eInspections")),
        raw_name=name,
        raw_address=address,
    )


def normalize_all(records: Iterable[dict]) -> list[Station]:
    """Normalize every record, dropping repeats of a station number (first wins)."""
    by_id: dict[int, Station] = {}
    duplicates = 0
    unknown_classes: set[str] = set()
    for raw in records:
        station = normalize_record(raw)
        if station.id in by_id:
            duplicates += 1
            continue
        by_id[station.id] = station
        unknown_classes.update(code for code in station.classes if code not in CLASS_ORDER)
    if duplicates:
        log.warning("dropped %d duplicate station records", duplicates)
    if unknown_classes:
        log.warning("unknown vehicle class codes: %s", ", ".join(sorted(unknown_classes)))
    return [by_id[key] for key in sorted(by_id)]


def write_stations(stations: Iterable[Station], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [station.to_dict() for station in stations]
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")


def read_stations(path: Path) -> list[Station]:
    return [Station.from_dict(item) for item in json.loads(path.read_text(encoding="utf-8"))]
