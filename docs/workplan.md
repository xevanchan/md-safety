# Workplan: Maryland inspection station finder

Date: 2026-11-23
Status: Draft for review

## Goal

A free website that shows every licensed Maryland vehicle safety inspection station on a
map and lists them by distance from the visitor. The official lookup only offers a paged
table filtered by name, county, city or ZIP, with no map and no "nearest to me".

Success looks like: open the site on a phone, tap "Use my location", and within two
seconds see the nearest stations sorted by distance, with pins on a map, a phone number
you can tap, and a directions link. Zero running cost.

## What we learned about the data (checked 2026-11-23)

Source page: https://egov.maryland.gov/msp/msis/lookup/stations (Maryland State Police,
Maryland Safety Inspection System, "MSIS", built by Tyler Maryland).

- It is a Vue single-page app. The table is filled by one JSON call:
  `POST https://egov.maryland.gov/msp/msis/api/Stations/PublicStationSearch`.
- Request body: a DataTables server-side payload (`draw`, `start`, `length`, `order`,
  `columns`, `search`) merged with the page's filter object
  `{stationName, county, city, zip, types: []}`. The UI offers page sizes of 10 and 25,
  but the API honours a larger `length`: on 2026-11-23 one request with `length: 2000`
  returned all 1,520 stations, so a refresh costs the state a single request.
- Response: `{"data": [...], "recordsFiltered": 1520}`. One record looks like:

  ```json
  {"stationNumber": 2, "tradingName": "PEP BOYS #65", "address": "1120 WEST PATRICK STREET",
   "city": "FREDERICK", "state": "Maryland", "zipCode": "21703", "phone": "(301)6957666",
   "types": "A, A/M Trailer, T", "eInspections": true}
  ```

- 1,520 stations today. No coordinates, so geocoding is on us.
- First snapshot (2026-11-23): every station is in Maryland, every record has a phone
  number, 1,519 offer e-Inspection, eight ZIPs carry a +4 suffix, and no station number
  repeats.
- Vehicle classes (from the page's "What is this?" modal and its lookups module):
  A passenger vehicles and light trucks, B any trailer, C heavy trucks and buses,
  M motorcycles, TL light trailers, R motor homes, F (undocumented), plus the display-only
  label "A/M Trailer". Records never use `TL`; 1,459 of 1,520 stations carry `T`, so `T`
  is the trailer class in the data and the site should label it "Trailer".
- Data hygiene needed: names and addresses are mixed UPPERCASE and Title Case; phone
  formats vary (`(301)6957666`, `(410) 363-3333`, `410-968-0606`); `types` is a comma
  string, not a list.
- No existing open dataset of safety inspection stations was found on data.gov or the
  Maryland open data portal. Only MVA office and VEIP emissions locations are published
  (see References). Worth a ten-minute re-check on opendata.maryland.gov before coding.
- robots.txt on egov.maryland.gov disallows everything except an allow list.
  `/msp/vsi/lookup` is on the allow list and redirects to `/msp/msis/Lookup`, so the
  intent appears to be that the lookup is public, but `/msp/msis/` itself is not listed.
  Treat this as a courtesy signal, not a green light.

### Data access stance (decided 2026-11-23: option 2, see decisions/0002)

Two complementary paths. Doing both is cheap.

1. Ask. Email the Automotive Safety Enforcement Division (the page lists
   MSP.ASED@maryland.gov, 410-768-7388) for a periodic export or permission to pull the
   public list. A Maryland Public Information Act request is the formal fallback. Station
   licence records are public facts about licensed businesses, which helps.
2. Pull politely. One full pass at most once a month, 25 records per request with a
   one-second pause, a User-Agent that names the project and a contact address, cached
   locally so nothing is fetched twice. Stop if the site asks us to.

## Architecture (proposed)

Static site plus an offline data pipeline. No server, no database, no accounts.

```
MSIS API ──fetch──▶ data/raw/latest.json ──normalize──▶ clean records
   ──geocode (Census batch, cached)──▶ web/data/stations.json ──▶ static site on GitHub Pages
                                                                     │
                                            browser: geolocation ──▶ haversine sort ──▶ map + list
```

- Pipeline: this repo, Python managed by uv (`src/md_safety/`). Run by hand or by a
  monthly GitHub Actions job that commits the refreshed JSON.
- Site: plain HTML, CSS and JavaScript in `web/`, no build step. Loads one
  `stations.json` (about 1,520 records, roughly 300 KB raw, around 60 KB gzipped),
  computes straight-line distance in the browser, sorts, renders.
- Why static: it costs nothing, there is nothing to patch at 2 a.m., and the visitor's
  location never leaves their browser.

### Free building blocks

| Need | Choice | Why | Caveats |
| --- | --- | --- | --- |
| Geocode 1,520 addresses | US Census Geocoder, batch endpoint | Free, no key, up to 10,000 addresses per CSV, official US address data | Expect a few percent unmatched; keep a fallback and a manual overrides file |
| Geocode fallback | Centre of the station's ZIP code (Census ZCTA gazetteer, bundled) | Offline, no second service to depend on | Approximate; the site flags it |
| Map | MapLibre GL JS with OpenFreeMap tiles | No key, no advertised caps, native point clustering | Verify current OpenFreeMap terms. Leaflet plus OSM raster tiles is the simplest fallback, but OSM's tile policy is for light use only |
| Visitor location | Browser Geolocation API | Free, precise | Needs HTTPS and permission; always offer a typed fallback |
| Typed fallback | Bundled Maryland ZIP centroid table (Census ZCTA gazetteer, about 470 rows) | Works offline, instant, no API | Centroid accuracy is enough for sorting, not for walking |
| Directions | Google Maps / Apple Maps URL with the address | Free, no key | Opens another app; that is what people want anyway |
| Hosting | GitHub Pages from a public repo | Free, HTTPS, deploys on push | A custom domain is the only possible cost |
| Scheduled refresh | GitHub Actions cron | Free for public repos | Needs permission to commit back to the repo |

## Phases

Checkboxes are the task list. Each phase ends with tests passing and a CHANGELOG line.

### Phase 0: decide and record (one short session)

- [x] Pick the data access stance above and send the ASED email if we go that route.
      Record it as `docs/decisions/0002-data-access.md`.
- [x] Record the architecture as `docs/decisions/0003-static-site-and-offline-pipeline.md`.
- [x] Add `web/` and `data/` to the layout tables in README.md and CLAUDE.md.
- [x] Create the public GitHub repo (needed for Pages and Actions).

### Phase 1: fetch and normalize (one or two sessions)

- [x] `uv add httpx`. Write `src/md_safety/fetch.py`: builds the DataTables payload,
      pages through results, one-second pause, retries with backoff, project User-Agent,
      writes `data/raw/latest.json` plus a dated copy. Run it once by hand and check
      whether a large `length` returns everything in one call.
- [x] Write `src/md_safety/models.py`: a `Station` dataclass with `id` (station number),
      `name`, `address`, `city`, `zip`, `phone`, `classes: list[str]`, `e_inspection: bool`,
      later `lat`, `lon`, `geocode_source`.
- [x] Write `src/md_safety/normalize.py`: title-case names and streets (keep the raw
      values too), phone digits to `(xxx) xxx-xxxx`, split `types` into classes, map
      `T` to `TL` once confirmed, drop duplicates by station number.
- [x] Save the ten records captured today as `tests/fixtures/public_station_search_page1.json`
      and test normalize against them. Test the payload builder and paging logic with a
      fake transport, never against the live site.
- [x] CLI: `md-safety fetch` and `md-safety normalize` subcommands in `cli.py`.

### Phase 2: geocode and build (done 2026-11-24)

Kept deliberately small: one geocoder, one output file, two plain checks.

- [x] `src/md_safety/geocode.py`: one Census batch request (id, street, city, state, zip),
      results cached in `data/geocoded/cache.csv` by address so a refresh only geocodes new
      addresses. First run: 1,432 of 1,520 matched, in six seconds.
- [x] Misses fall back to the centre of their ZIP code from `data/md_zips.csv` (477 Maryland
      ZCTAs from the Census gazetteer) and are marked approximate. `data/overrides.csv` wins
      over everything for hand-fixed coordinates. No second geocoding service.
- [x] Two checks in `md-safety build`: fewer than two percent of stations without
      coordinates, and a station count within ten percent of the previous build. Points
      outside Maryland count as misses.
- [x] `md-safety build` writes `web/data/stations.json` only (no GeoJSON) with
      `generated_at`, `fetched_at`, `source_url`, counts, and the per-station fields the site
      needs, including an `approx` flag.
- [x] README, data/README and CHANGELOG describe the full pipeline.

Open: station 1760 (Cavetown, ZIP 21720) has no Census match and its ZIP has no ZCTA, so
it needs a row in `data/overrides.csv`.

### Phase 3: the website (two or three sessions)

- [ ] `web/index.html`, `web/app.js`, `web/styles.css`. Mobile-first: people use this
      standing in a parking lot.
- [ ] Map of all stations with clustering; click a pin to highlight the list entry and
      vice versa.
- [ ] "Use my location" button: geolocation, haversine distance in miles, list sorted
      nearest first, show the top 25 with a "show more" control.
- [ ] Typed fallback: ZIP box backed by the bundled centroid table; optional full-address
      search via Nominatim, triggered only by the visitor pressing Search.
- [ ] Filters: vehicle class (default A, which is cars and light trucks), e-Inspection
      only, name search.
- [ ] Each result: name, address, tap-to-call phone, classes, e-Inspection badge, distance,
      directions link.
- [ ] Footer: "Data from Maryland State Police MSIS, last updated <date>. Licences change;
      confirm with the station or the official lookup." Link to the official page and to
      the map attribution.
- [ ] Accessibility pass: keyboard navigation of the list, visible focus, colour contrast,
      labels on inputs.
- [ ] Manual test on a real phone over cellular.

### Phase 4: deploy and automate (one session)

- [ ] GitHub Pages serving `web/` from `main`.
- [ ] `.github/workflows/ci.yml`: ruff and pytest on every push and pull request.
- [ ] `.github/workflows/refresh-data.yml`: monthly cron, runs `uv run md-safety build`,
      commits `web/data/` only if it changed, which redeploys Pages.
- [ ] Privacy note on the site: location is used in the browser only; no analytics.
- [ ] Optional custom domain.

### Phase 5: stretch (only after people use it)

- Driving time instead of straight-line distance for the top ten results. The public
  OSRM demo server is not for production use, so this needs a free-tier routing key.
- Add the VEIP emissions test locations as a second layer, since registration usually
  needs both inspections. That dataset is already open with coordinates.
- Month-over-month diff: new and removed stations.
- Shareable links (`?zip=21703`), install-to-home-screen support.

## Repo layout after Phase 4

```
md-safety/
├── src/md_safety/          fetch.py  normalize.py  geocode.py  build.py  models.py  cli.py
├── data/
│   ├── raw/                latest.json and dated snapshots from MSIS
│   ├── geocoded/           census.csv cache
│   └── overrides.csv       hand-fixed coordinates
├── web/                    the static site, deployed as-is
│   ├── index.html  app.js  styles.css
│   └── data/               stations.json, stations.geojson, md-zips.json (built, committed)
├── tests/fixtures/         captured API responses
└── .github/workflows/      ci.yml, refresh-data.yml
```

`data/` and `web/data/` are committed on purpose: the site has no build step, and a
reviewer can diff what changed in each monthly refresh.

## Risks and open questions

| Risk | Mitigation |
| --- | --- |
| The API changes shape or starts blocking us | Fixture-based tests catch shape changes; count-drop gate stops a bad build from deploying; the ASED conversation gives us a human to call |
| Terms of use or robots.txt objection | Decide in Phase 0; low volume; stop on request |
| Geocoder puts a rural address in the wrong place | Match-quality column in the output, bounding-box gate, overrides file, "report a problem" link on the site |
| Map tile provider changes terms | Tiles are one line of config; PMTiles self-hosting on Pages is the free escape hatch |
| `T` versus `TL` class code | Check a known trailer-only station or ask ASED before filtering on it |
| Stale licences mislead someone | Dated footer, monthly refresh, link to the official lookup |

## Definition of done for the MVP (Phases 1 to 4)

- On a phone, "Use my location" shows the nearest stations sorted by distance with pins,
  phone links and directions, in under two seconds on a cellular connection.
- Data is never more than about 35 days old and refreshes without anyone touching it.
- Nothing costs money. No keys, no servers, no accounts beyond GitHub.

Rough effort: four to six focused sessions for the MVP.

## References

- Official lookup: https://egov.maryland.gov/msp/msis/lookup/stations
- MSP page on inspection stations and mechanics (about 1,600 licensed stations, ASED
  oversight): https://mdsp.maryland.gov/safety-prevention/vehicle-safety-inspections/inspection-stations-and-mechanics
- Census Geocoder services and batch limits: https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html
- Census batch form (10,000 records, 5 MB): https://geocoding.geo.census.gov/geocoder/geographies/addressbatch?form
- VEIP (emissions) service locations open dataset, with coordinates: https://catalog.data.gov/dataset/veip-service-locations
- Maryland iMAP MVA facilities layer: https://mdgeodata.md.gov/imap/rest/services/Transportation/MD_MVAFacilities/MapServer/layers
