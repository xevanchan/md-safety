from importlib.metadata import version

from md_safety import __version__
from md_safety.cli import main


def test_package_version_matches_pyproject():
    assert version("md-safety") == __version__


def test_main_runs_and_exits_cleanly(capsys):
    assert main([]) == 0
    assert "md-safety" in capsys.readouterr().out
