import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from md_safety.build import (
    BuildError,
    build_payload,
    check,
    previous_count,
    site_record,
    write_payload,
    write_zips,
)
from md_safety.models import Station


def make_station(id: int, lat: float | None = 39.0, lon: float | None = -76.0) -> Station:
    return Station(
        id=id,
        name=f"Station {id}",
        address="1 Main Street",
        city="Frederick",
        state="MD",
        zip="21703",
        phone="(301) 555-0100",
        classes=("A", "T"),
        e_inspection=True,
        raw_name=f"STATION {id}",
        raw_address="1 MAIN STREET",
        lat=lat,
        lon=lon,
        geocode_source=None if lat is None else "census",
    )


def test_check_accepts_healthy_data():
    stations = [make_station(i) for i in range(1, 101)] + [make_station(101, None, None)]
    check(stations, previous_count=100)  # 1% unmatched, 1% growth


def test_check_rejects_too_many_unmatched():
    stations = [make_station(1), make_station(2), make_station(3, None, None)]
    with pytest.raises(BuildError, match="1 of 3 stations have no coordinates"):
        check(stations, previous_count=None)


def test_check_rejects_large_count_change():
    stations = [make_station(i) for i in range(1, 81)]
    with pytest.raises(BuildError, match="went from 100 to 80"):
        check(stations, previous_count=100)
    check(stations, previous_count=None)  # first build has nothing to compare against


def test_site_record_rounds_and_drops_raw_fields():
    record = site_record(make_station(1, lat=39.123456789, lon=-76.987654321))
    assert record == {
        "id": 1,
        "name": "Station 1",
        "address": "1 Main Street",
        "city": "Frederick",
        "zip": "21703",
        "phone": "(301) 555-0100",
        "classes": ["A", "T"],
        "e_inspection": True,
        "lat": 39.12346,
        "lon": -76.98765,
        "approx": False,
    }
    assert site_record(make_station(2, None, None))["lat"] is None
    assert site_record(replace(make_station(3), geocode_source="zip"))["approx"] is True


def test_build_and_write_payload(tmp_path):
    stations = [make_station(1), make_station(2, None, None)]
    when = datetime(2026, 11, 23, 20, 0, tzinfo=UTC)
    payload = build_payload(stations, fetched_at="2026-11-23T18:17:00+00:00", generated_at=when)
    assert payload["generated_at"] == "2026-11-23T20:00:00+00:00"
    assert payload["fetched_at"] == "2026-11-23T18:17:00+00:00"
    assert payload["count"] == 2
    assert payload["located"] == 1
    assert payload["source_url"].startswith("https://egov.maryland.gov/")

    out = tmp_path / "web" / "data" / "stations.json"
    assert previous_count(out) is None
    write_payload(payload, out)
    assert previous_count(out) == 2
    assert b"\r\n" not in out.read_bytes()
    assert json.loads(out.read_text(encoding="utf-8"))["stations"][0]["name"] == "Station 1"


def test_write_zips(tmp_path):
    source = tmp_path / "md_zips.csv"
    source.write_text(
        "zip,lat,lon\n21703,39.391234,-77.461234\n20601,38.62,-76.86\n", encoding="utf-8"
    )
    out = tmp_path / "web" / "data" / "zips.json"
    assert write_zips(source, out) == 2
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "21703": [39.391234, -77.461234],
        "20601": [38.62, -76.86],
    }
    assert b"\r\n" not in out.read_bytes()
