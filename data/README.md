# data/

Inputs and intermediate outputs of the pipeline. Everything here is committed so that
tests, re-runs and reviews never need the live site (decision 0002).

| Path | Written by | Contents |
| --- | --- | --- |
| `raw/latest.json` | `md-safety fetch` | The most recent snapshot straight from MSIS, wrapped as `{fetched_at, source, count, records}`. |
| `raw/stations-YYYY-MM-DD.json` | `md-safety fetch` | Dated copy of the same snapshot, so refreshes can be diffed. |
| `normalized/stations.json` | `md-safety normalize` | Cleaned station records; fields are documented in `src/md_safety/models.py`. |
| `geocoded/cache.csv` | `md-safety geocode` | Census geocoder results keyed by address, so a refresh only geocodes new addresses. |
| `geocoded/stations.json` | `md-safety geocode` | Normalized records plus `lat`, `lon` and `geocode_source` (`census`, `zip` or `override`). |
| `md_zips.csv` | by hand, from the Census gazetteer | Centre of each Maryland ZIP code: the fallback for addresses the geocoder cannot place. |
| `overrides.csv` | by hand | `id, lat, lon, note` for stations whose coordinates need fixing. Always wins. |

`md-safety fetch` is the only command that talks to the state's site. Run it at most monthly.
`md-safety geocode` calls the Census Bureau only for addresses missing from the cache.

`md_zips.csv` is the 2024 Census Gazetteer ZCTA file
(https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip)
filtered to ZIP codes 20600 to 21999 inside Maryland's bounding box.
