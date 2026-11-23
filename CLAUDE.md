# md-safety: working conventions

Python project managed with uv. Source in `src/md_safety/`, tests in `tests/`.

## Commands

- Install or sync the environment: `uv sync`
- Tests: `uv run pytest`
- Lint and format (run both before committing): `uv run ruff check .` then `uv run ruff format .`
- Run the CLI: `uv run md-safety`
- Add a dependency: `uv add <pkg>`. Dev-only: `uv add --dev <pkg>`.
- Never `pip install` into the venv directly. `uv.lock` is committed and is the source of truth.

## Where things go

- Importable code: `src/md_safety/`. No Python modules at the repo root.
- Tests: `tests/test_<module>.py`, mirroring the package layout.
- Scripts that are not part of the package: `scripts/`.
- Pipeline data (raw MSIS snapshots, geocode cache, overrides): `data/`. Committed. Tests never fetch live data.
- The static site: `web/`. Plain HTML, CSS and JS with no build step. Built JSON goes to `web/data/`.
- Documentation: `docs/`. Hard-to-reverse decisions: `docs/decisions/NNNN-short-title.md`,
  using the template in `docs/decisions/README.md`.
- Anything a user would notice: one line under *Unreleased* in `CHANGELOG.md`.
- Local experiments: `scratch/` (gitignored).
- Secrets and machine-specific config: `.env` (gitignored). Never commit credentials.

## Style

- Python 3.12+ syntax. Type hints on public functions.
- Ruff owns lint and format; its config is in `pyproject.toml`. Do not hand-format around it.
- Small, focused modules. Prefer a new module over a very long file.
- Tests are plain pytest functions and fixtures, not unittest classes.

## Git

- Default branch is `main`. Work on short-lived branches and merge when tests and ruff pass.
- Commit subject: imperative mood, under 72 characters. Body explains why when it is not obvious.
