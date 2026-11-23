# data/

Inputs and intermediate outputs of the pipeline. Everything here is committed so that
tests, re-runs and reviews never need the live site (decision 0002).

| Path | Written by | Contents |
| --- | --- | --- |
| `raw/latest.json` | `md-safety fetch` | The most recent snapshot straight from MSIS, wrapped as `{fetched_at, source, count, records}`. |
| `raw/stations-YYYY-MM-DD.json` | `md-safety fetch` | Dated copy of the same snapshot, so refreshes can be diffed. |
| `normalized/stations.json` | `md-safety normalize` | Cleaned station records; fields are documented in `src/md_safety/models.py`. |
| `geocoded/` | `md-safety geocode` (Phase 2) | Geocoder cache keyed by address. |
| `overrides.csv` | by hand (Phase 2) | Coordinates for stations the geocoders get wrong. |

`md-safety fetch` is the only command that talks to the state's site. Run it at most monthly.
