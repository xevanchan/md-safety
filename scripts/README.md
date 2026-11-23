# scripts/

One-off and operational scripts that are not part of the `md_safety` package:
data pulls, migrations, maintenance jobs, experiments worth keeping.

- Run them inside the project environment: `uv run python scripts/<name>.py`
- Give each a docstring at the top saying what it does and when to run it.
- If something here becomes reusable, move it into `src/md_safety/` and add tests.
