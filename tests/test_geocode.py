from dataclasses import replace

import httpx
import pytest

from md_safety.geocode import (
    CENSUS_BATCH_URL,
    address_key,
    census_batch_csv,
    geocode_stations,
    in_maryland,
    parse_census_results,
    read_cache,
    write_cache,
)
from md_safety.models import Station


def make_station(id: int, address: str = "1 Main Street", city: str = "Frederick") -> Station:
    return Station(
        id=id,
        name=f"Station {id}",
        address=address,
        city=city,
        state="MD",
        zip="21703",
        phone=None,
        classes=("A",),
        e_inspection=True,
        raw_name=f"STATION {id}",
        raw_address=address.upper(),
    )


CENSUS_REPLY = (
    '"1","1 Main Street, Frederick, MD, 21703","Match","Exact",'
    '"1 MAIN ST, FREDERICK, MD, 21703","-77.41,39.41","6360","L"\n'
    '"2","9 Nowhere Road, Frederick, MD, 21703","No_Match"\n'
    '"3","5 Split Way, Frederick, MD, 21703","Tie"\n'
    '"4","1 Far Street, Frederick, MD, 21703","Match","Non_Exact",'
    '"1 FAR ST, SOMEWHERE, TX, 75001","-96.80,32.78","1","R"\n'
)


def test_address_key_ignores_case_and_spacing():
    a = make_station(1, address="1120 West Patrick Street")
    b = make_station(2, address="1120  WEST PATRICK  STREET")
    assert address_key(a) == address_key(b) == "1120 WEST PATRICK STREET|FREDERICK|MD|21703"


def test_in_maryland_bounds():
    assert in_maryland(39.41, -77.41)
    assert not in_maryland(32.78, -96.80)


def test_census_batch_csv_has_no_header():
    text = census_batch_csv([make_station(7, address="427-A East Diamond Avenue")])
    assert text == "7,427-A East Diamond Avenue,Frederick,MD,21703\n"


def test_parse_census_results_keeps_only_matches():
    assert parse_census_results(CENSUS_REPLY) == {1: (39.41, -77.41), 4: (32.78, -96.80)}


def test_cache_roundtrip_uses_unix_line_endings(tmp_path):
    path = tmp_path / "geocoded" / "cache.csv"
    write_cache(path, {"B|X|MD|1": (39.5, -76.5), "A|X|MD|1": (38.123456789, -75.1)})
    assert read_cache(path) == {"A|X|MD|1": (38.123457, -75.1), "B|X|MD|1": (39.5, -76.5)}
    assert b"\r\n" not in path.read_bytes()
    assert read_cache(tmp_path / "missing.csv") == {}


def test_geocode_stations_uses_overrides_then_cache_then_census(tmp_path):
    stations = [
        make_station(1),
        make_station(2, address="9 Nowhere Road"),
        make_station(3, address="5 Split Way"),
        make_station(4, address="1 Far Street"),
        make_station(5, address="2 Cached Lane"),
        make_station(6, address="3 Fixed Court"),
    ]
    cache_path = tmp_path / "cache.csv"
    write_cache(cache_path, {address_key(stations[4]): (39.0, -76.0)})
    overrides_path = tmp_path / "overrides.csv"
    overrides_path.write_text("id,lat,lon,note\n6,38.9,-76.9,moved in 2026\n", encoding="utf-8")

    requests: list[httpx.Request] = []

    def census(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=CENSUS_REPLY)

    with httpx.Client(transport=httpx.MockTransport(census)) as client:
        located = geocode_stations(
            stations, cache_path=cache_path, overrides_path=overrides_path, client=client
        )

    assert len(requests) == 1
    assert requests[0].url == CENSUS_BATCH_URL
    body = requests[0].content
    assert b"1,1 Main Street" in body
    assert b"2 Cached Lane" not in body  # cached, so not sent
    assert b"3 Fixed Court" not in body  # overridden, so not sent

    by_id = {s.id: s for s in located}
    assert (by_id[1].lat, by_id[1].lon, by_id[1].geocode_source) == (39.41, -77.41, "census")
    assert by_id[2].lat is None  # No_Match
    assert by_id[3].lat is None  # Tie
    assert by_id[4].lat is None  # matched, but in Texas
    assert (by_id[5].lat, by_id[5].geocode_source) == (39.0, "census")
    assert (by_id[6].lat, by_id[6].lon, by_id[6].geocode_source) == (38.9, -76.9, "override")
    assert address_key(stations[0]) in read_cache(cache_path)
    assert address_key(stations[3]) not in read_cache(cache_path)


def test_zip_centre_fallback_is_marked_approximate(tmp_path):
    zips = tmp_path / "md_zips.csv"
    zips.write_text("zip,lat,lon\n21703,39.39,-77.46\n", encoding="utf-8")
    stations = [make_station(1), replace(make_station(2), zip="21999")]
    located = geocode_stations(
        stations, cache_path=tmp_path / "c.csv", overrides_path=tmp_path / "o.csv", zips_path=zips
    )
    assert (located[0].lat, located[0].lon, located[0].geocode_source) == (39.39, -77.46, "zip")
    assert located[1].lat is None  # ZIP not in the table


def test_geocode_stations_offline_never_calls_the_network(tmp_path):
    def explode(_: httpx.Request) -> httpx.Response:
        raise AssertionError("offline mode must not make requests")

    located = geocode_stations(
        [make_station(1)], cache_path=tmp_path / "cache.csv", overrides_path=tmp_path / "o.csv"
    )
    assert located[0].lat is None
    assert not (tmp_path / "cache.csv").exists()


def test_census_http_error_propagates(tmp_path):
    def broken(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    with (
        httpx.Client(transport=httpx.MockTransport(broken)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        geocode_stations(
            [make_station(1)],
            cache_path=tmp_path / "cache.csv",
            overrides_path=tmp_path / "o.csv",
            client=client,
        )
