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

## Pipeline

```powershell
uv run md-safety normalize     # data/raw/latest.json -> data/normalized/stations.json
uv run md-safety geocode       # add coordinates (Census geocoder, cached) -> data/geocoded/
uv run md-safety build         # sanity checks, then web/data/stations.json for the site
```

`uv run md-safety fetch` refreshes `data/raw/` from the state's lookup in a single request.
It is deliberately rare, at most monthly (decision 0002); everything else runs from the
committed snapshot, and the tests never touch the network. `geocode` only calls the Census
Bureau for addresses missing from `data/geocoded/cache.csv`; add `--offline` to skip the
network entirely.

## Site

The site is `web/`: one HTML file, one stylesheet, one script, and the JSON that `build`
writes into `web/data/`. There is no build step. To try it locally:

```powershell
uv run python -m http.server 8000 -d web
```

then open http://localhost:8000. Map tiles come from OpenFreeMap, so it needs internet.

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
