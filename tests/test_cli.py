import json
from importlib.metadata import version
from pathlib import Path

from md_safety import __version__, cli
from md_safety.fetch import DEFAULT_PAGE_SIZE, FetchError, save_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "public_station_search_page1.json"


def test_package_version_matches_pyproject():
    assert version("md-safety") == __version__


def test_no_command_prints_help(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "md-safety" in out
    assert "fetch" in out
    assert "normalize" in out


def test_normalize_command_writes_clean_stations(tmp_path, capsys):
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))["data"]
    latest = save_snapshot(records, tmp_path / "data")
    output = tmp_path / "data" / "normalized" / "stations.json"
    assert cli.main(["normalize", "--input", str(latest), "--output", str(output)]) == 0
    stations = json.loads(output.read_text(encoding="utf-8"))
    assert len(stations) == 10
    assert stations[0]["name"] == "Pep Boys #65"
    assert "wrote 10 stations" in capsys.readouterr().out


def test_normalize_command_without_snapshot_fails(tmp_path):
    missing = tmp_path / "nope.json"
    output = tmp_path / "out.json"
    assert cli.main(["normalize", "--input", str(missing), "--output", str(output)]) == 1


def test_fetch_command_reports_failure(monkeypatch, tmp_path):
    def boom(*_args, **_kwargs):
        raise FetchError("site said no")

    monkeypatch.setattr(cli, "fetch_stations", boom)
    assert cli.main(["fetch", "--data-dir", str(tmp_path)]) == 1


def test_fetch_command_saves_snapshot(monkeypatch, tmp_path, capsys):
    def fake_fetch(data_dir, *, page_size, delay):
        assert page_size == DEFAULT_PAGE_SIZE
        assert delay == 1.0
        return save_snapshot([{"stationNumber": 1}], data_dir)

    monkeypatch.setattr(cli, "fetch_stations", fake_fetch)
    assert cli.main(["fetch", "--data-dir", str(tmp_path)]) == 0
    assert (tmp_path / "raw" / "latest.json").exists()
    assert "saved 1 stations" in capsys.readouterr().out
