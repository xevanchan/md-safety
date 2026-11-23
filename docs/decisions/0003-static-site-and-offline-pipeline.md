# 0003. Static site fed by an offline data pipeline

Date: 2026-11-23
Status: Accepted

## Context
The product must be free to run indefinitely and maintainable by one person. Visitors need
the nearest stations to their location. The data is small (about 1,500 records) and changes
slowly, since it tracks business licences.

## Decision
- Pipeline in this repo, Python managed by uv: fetch, normalize, geocode, then build
  `web/data/stations.json`. It runs by hand or on a monthly GitHub Actions schedule that
  commits refreshed data.
- Site: static HTML, CSS and JavaScript in `web/`, no build step, served by GitHub Pages.
  Distance sorting runs in the browser from the Geolocation API; a bundled Maryland ZIP
  centroid table is the typed fallback.
- Geocoding: US Census batch geocoder with a committed cache, then Nominatim, then a manual
  overrides file for the misses.
- Map: MapLibre GL JS with OpenFreeMap tiles. Leaflet with OpenStreetMap raster tiles is the
  fallback if that provider's terms change.
- Built data in `data/` and `web/data/` is committed on purpose.

## Consequences
- No hosting cost, no server, no database, no secrets. The only network calls at runtime
  are map tiles and any address lookup the visitor triggers.
- The visitor's location never leaves their browser.
- Committing data grows the repo by a few hundred kilobytes per refresh. Acceptable;
  revisit if it becomes a nuisance.
- No build step means plain JavaScript and no bundler. Keep `app.js` small; add a bundler
  only if the site outgrows it.
