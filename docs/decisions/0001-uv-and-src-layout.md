# 0001. Manage the project with uv and a src layout

Date: 2026-11-23
Status: Accepted

## Context
The project is starting from scratch and the goal is for it to stay organised as it grows.
Python tooling choices made early are painful to change later.

## Decision
- One tool, uv, manages the Python version (`.python-version`), the virtual environment
  (`.venv/`), dependencies (`pyproject.toml`) and the lockfile (`uv.lock`).
- Code lives under `src/md_safety/` and is installed into the environment as a package,
  so imports work the same from tests, scripts and the CLI.
- Ruff handles both linting and formatting. Pytest runs the tests.

## Consequences
- Every command runs through `uv run ...`; nobody needs to activate the venv by hand.
- Nothing importable lives at the repo root, so the root stays small and readable.
- `uv.lock` is committed, so installs are reproducible on another machine.
