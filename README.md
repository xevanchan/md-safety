# md-safety

Find the closest Maryland vehicle safety inspection station: every licensed station on a
map, sorted by distance from you. Free to use and free to run.

The build plan, with what we know about the data, lives in [docs/workplan.md](docs/workplan.md).

## Quick start

Requires [uv](https://docs.astral.sh/uv/). The Python version is pinned in `.python-version`
and the environment lives in `.venv/`, both handled by uv.

```powershell
uv sync                 # create .venv and install everything, including dev tools
uv run md-safety        # run the CLI
uv run pytest           # run the tests
uv run ruff check .     # lint
uv run ruff format .    # format
```

## Layout

| Path | What goes here |
| --- | --- |
| `src/md_safety/` | The package. All importable code lives here, nothing at the repo root. |
| `tests/` | Pytest tests. Mirror the package: `src/md_safety/foo.py` is tested by `tests/test_foo.py`. |
| `scripts/` | One-off or operational scripts that are not part of the package. |
| `data/` | Pipeline inputs and caches: raw MSIS snapshots, geocoder cache, manual coordinate overrides. Committed on purpose. |
| `web/` | The static site, deployed as-is by GitHub Pages. Built JSON lives in `web/data/`. |
| `docs/` | Longer-form documentation. `docs/decisions/` holds numbered decision records. |
| `scratch/` | Local experiments. Ignored by git, so nothing here is ever committed. |
| `CHANGELOG.md` | User-facing changes, newest first. Add a line under *Unreleased* with each change. |
| `CLAUDE.md` | Working conventions for Claude Code and anyone else contributing. |

## Everyday commands

| Task | Command |
| --- | --- |
| Add a dependency | `uv add requests` |
| Add a dev-only dependency | `uv add --dev pytest-cov` |
| Remove a dependency | `uv remove requests` |
| Run a script inside the venv | `uv run python scripts/example.py` |
| Upgrade all pinned versions | `uv lock --upgrade` then `uv sync` |

## Conventions

- Keep the repo root to config and docs. Code goes in `src/`, tests in `tests/`.
- Every change that alters behaviour gets a test and a CHANGELOG line.
- Decisions that would be hard to reverse get a short record in `docs/decisions/`.
- Commit messages: short imperative subject (`Add input validation`), body only when the why is not obvious.
