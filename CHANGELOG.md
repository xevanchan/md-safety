# Changelog

Notable changes to md-safety, newest first. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project skeleton: uv-managed environment, src layout, pytest, ruff, decision log.
- Workplan for the station finder: data findings, architecture, phases (docs/workplan.md).
- Decision records for data access (0002) and the static-site architecture (0003); layout docs now cover data/ and web/.
- Pipeline: `md-safety fetch` (polite single-request MSIS pull) and `md-safety normalize`, plus the first committed snapshot of 1,520 stations.
- Geocoding and build: `md-safety geocode` (Census batch geocoder with a cache, ZIP-centre fallback, overrides) and `md-safety build` (two sanity checks, then `web/data/stations.json`). 1,519 of 1,520 stations located.
- Website: `web/` static page with a map of every station, "use my location" and ZIP search sorted by distance, a vehicle class filter, and phone and directions links.
