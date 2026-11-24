import json
from pathlib import Path

import pytest

from md_safety.models import Station
from md_safety.normalize import (
    clean_zip,
    format_phone,
    normalize_all,
    normalize_record,
    read_stations,
    smart_title,
    split_classes,
    state_code,
    write_stations,
)

FIXTURE = Path(__file__).parent / "fixtures" / "public_station_search_page1.json"


def fixture_records() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["data"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("PEP BOYS #65", "Pep Boys #65"),
        ("WALT EGER'S SERVICE CENTER INC.", "Walt Eger's Service Center Inc."),
        ("DARCARS NISSAN OF COLLEGE PARK", "Darcars Nissan of College Park"),
        ("Koons Volvo Cars White Marsh", "Koons Volvo Cars White Marsh"),
        ("427-A EAST DIAMOND AVENUE", "427-A East Diamond Avenue"),
        ("O'BRIEN AUTO LLC", "O'Brien Auto LLC"),
        ("DOWNTOWN BP", "Downtown BP"),
        ("JONES MOTORS DBA JBA CHEVROLET", "Jones Motors DBA JBA Chevrolet"),
        ("MCCARTHY TIRE (ANNAPOLIS)", "McCarthy Tire (Annapolis)"),
        ("1234 N CHARLES ST", "1234 N Charles St"),
        ("PO BOX 12", "PO Box 12"),
        ("21ST STREET GARAGE", "21st Street Garage"),
        ("THE SHOP", "The Shop"),
        ("  DOUBLE  SPACE ", "Double Space"),
        ("", ""),
    ],
)
def test_smart_title(raw, expected):
    assert smart_title(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(301)6957666", "(301) 695-7666"),
        ("(410) 363-3333", "(410) 363-3333"),
        ("410-968-0606", "(410) 968-0606"),
        ("1-410-968-0606", "(410) 968-0606"),
        ("call shop", "call shop"),
        ("", None),
        (None, None),
    ],
)
def test_format_phone(raw, expected):
    assert format_phone(raw) == expected


def test_split_classes_orders_and_dedupes():
    assert split_classes("A, A/M Trailer, T") == ("A", "T", "A/M Trailer")
    assert split_classes("T, A, A, M") == ("A", "M", "T")
    assert split_classes("") == ()
    assert split_classes(None) == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Maryland", "MD"), ("md", "MD"), ("Virginia", "VA"), ("Narnia", "Narnia"), (None, "")],
)
def test_state_code(raw, expected):
    assert state_code(raw) == expected


def test_clean_zip():
    assert clean_zip("21703") == "21703"
    assert clean_zip("21703-1234") == "21703"
    assert clean_zip(" 2170 ") == "2170"


def test_normalize_record_from_fixture():
    station = normalize_record(fixture_records()[0])
    assert station == Station(
        id=2,
        name="Pep Boys #65",
        address="1120 West Patrick Street",
        city="Frederick",
        state="MD",
        zip="21703",
        phone="(301) 695-7666",
        classes=("A", "T", "A/M Trailer"),
        e_inspection=True,
        raw_name="PEP BOYS #65",
        raw_address="1120 WEST PATRICK STREET",
    )


def test_normalize_all_sorts_and_keeps_human_casing():
    stations = normalize_all(fixture_records())
    assert [s.id for s in stations] == [2, 14, 17, 26, 54, 71, 87, 146, 147, 152]
    koons = stations[1]
    assert koons.name == "Koons Volvo Cars White Marsh"
    assert koons.city == "White Marsh"
    assert stations[2].name == "Walt Eger's Service Center Inc."


def test_normalize_all_drops_duplicate_ids_keeping_first():
    records = fixture_records()[:2]
    twin = dict(records[0], tradingName="SOMEONE ELSE")
    stations = normalize_all([*records, twin])
    assert [s.id for s in stations] == [2, 14]
    assert stations[0].name == "Pep Boys #65"


def test_write_and_read_stations_roundtrip(tmp_path):
    stations = normalize_all(fixture_records())
    path = tmp_path / "out" / "stations.json"
    write_stations(stations, path)
    assert read_stations(path) == stations
    assert b"\r\n" not in path.read_bytes()
