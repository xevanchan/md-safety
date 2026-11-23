import json
from datetime import UTC, datetime

import httpx
import pytest

from md_safety import fetch
from md_safety.fetch import (
    FetchError,
    build_payload,
    fetch_all,
    load_snapshot,
    new_client,
    save_snapshot,
)


def make_records(count: int) -> list[dict]:
    return [
        {
            "stationNumber": number,
            "tradingName": f"STATION {number}",
            "address": f"{number} MAIN STREET",
            "city": "TOWN",
            "state": "Maryland",
            "zipCode": "21000",
            "phone": "4105550100",
            "types": "A",
            "eInspections": number % 2 == 0,
        }
        for number in range(1, count + 1)
    ]


class FakeServer:
    """Serves pages of ``records`` the way MSIS does, with optional failures and a size cap."""

    def __init__(self, records: list[dict], *, cap: int | None = None, fail_first: int = 0):
        self.records = records
        self.cap = cap
        self.fail_first = fail_first
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_first > 0:
            self.fail_first -= 1
            return httpx.Response(500, text="boom")
        payload = json.loads(request.content)
        start, length = payload["start"], payload["length"]
        if self.cap is not None:
            length = min(length, self.cap)
        page = self.records[start : start + length]
        return httpx.Response(200, json={"data": page, "recordsFiltered": len(self.records)})

    def payloads(self) -> list[dict]:
        return [json.loads(request.content) for request in self.requests]


def client_for(server: FakeServer) -> httpx.Client:
    return new_client(transport=httpx.MockTransport(server.handle))


def test_build_payload_matches_the_lookup_page():
    payload = build_payload(start=50, length=25, draw=3)
    assert payload["start"] == 50
    assert payload["length"] == 25
    assert payload["draw"] == 3
    assert payload["order"] == [{"column": 0, "dir": "asc"}]
    assert payload["columns"][0]["data"] == "stationNumber"
    assert payload["stationName"] == ""
    assert payload["types"] == []


def test_fetch_all_pages_through_everything_with_pauses():
    server = FakeServer(make_records(60))
    sleeps: list[float] = []
    with client_for(server) as client:
        records = fetch_all(client, page_size=25, delay=1.0, sleep=sleeps.append)
    assert [record["stationNumber"] for record in records] == list(range(1, 61))
    assert [payload["start"] for payload in server.payloads()] == [0, 25, 50]
    assert [payload["draw"] for payload in server.payloads()] == [1, 2, 3]
    assert sleeps == [1.0, 1.0]
    user_agent = server.requests[0].headers["User-Agent"]
    assert user_agent.startswith("md-safety/")
    assert fetch.REPO_URL in user_agent


def test_fetch_all_keeps_paging_when_server_caps_page_size():
    server = FakeServer(make_records(60), cap=25)
    with client_for(server) as client:
        records = fetch_all(client, page_size=2000, delay=0, sleep=lambda _: None)
    assert len(records) == 60
    assert [payload["start"] for payload in server.payloads()] == [0, 25, 50]


def test_fetch_all_retries_with_backoff_then_succeeds():
    server = FakeServer(make_records(30), fail_first=2)
    sleeps: list[float] = []
    with client_for(server) as client:
        records = fetch_all(client, page_size=25, delay=1.0, sleep=sleeps.append)
    assert len(records) == 30
    assert len(server.requests) == 4  # two failures, then two pages
    assert sleeps == [2.0, 4.0, 1.0]


def test_fetch_all_gives_up_after_three_consecutive_failures():
    server = FakeServer(make_records(30), fail_first=3)
    with client_for(server) as client, pytest.raises(FetchError, match="3 consecutive failures"):
        fetch_all(client, page_size=25, delay=0, sleep=lambda _: None)
    assert len(server.requests) == 3


def test_fetch_all_rejects_unexpected_shape():
    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"rows": []})

    with new_client(transport=httpx.MockTransport(handle)) as client, pytest.raises(FetchError):
        fetch_all(client, delay=0, max_failures=1, sleep=lambda _: None)


def test_save_snapshot_writes_latest_and_dated_copy(tmp_path):
    records = make_records(3)
    when = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)
    latest = save_snapshot(records, tmp_path, fetched_at=when)
    assert latest == tmp_path / "raw" / "latest.json"
    dated = tmp_path / "raw" / "stations-2026-11-23.json"
    assert dated.read_text(encoding="utf-8") == latest.read_text(encoding="utf-8")
    snapshot = load_snapshot(latest)
    assert snapshot["count"] == 3
    assert snapshot["fetched_at"] == "2026-11-23T15:00:00+00:00"
    assert snapshot["source"] == fetch.API_URL
    assert snapshot["records"] == records


def test_load_snapshot_rejects_other_json(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="not a station snapshot"):
        load_snapshot(path)
