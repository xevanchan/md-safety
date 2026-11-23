# 0002. Pull the station list from the public MSIS lookup, politely

Date: 2026-11-23
Status: Accepted

## Context
The only machine-readable source of licensed safety inspection stations is the JSON
endpoint behind the Maryland State Police MSIS public lookup
(`POST https://egov.maryland.gov/msp/msis/api/Stations/PublicStationSearch`). No open
dataset exists. The site's robots.txt disallows `/msp/msis/` while allowing the old lookup
URL that redirects there, so the signal is mixed. We considered asking the Automotive
Safety Enforcement Division for an export or permission and chose not to for now.

## Decision
Fetch the public list directly, with these rules built into the fetcher rather than left to
memory:

- At most one full pass per month in production. During development, work from the
  committed snapshot in `data/raw/` and from test fixtures; a live fetch is a deliberate,
  rare action and never part of the test suite.
- Page size 25, which is what the site's own UI offers, unless a single larger request is
  verified to work. At least one second between requests. Exponential backoff on errors
  and stop for the day after three consecutive failures.
- A User-Agent that names the project and links to its GitHub repository, so the site's
  operator can reach us.
- Commit each raw snapshot so re-runs, tests and diffs never need the live site.
- If the operator objects or starts blocking, stop and revisit this decision: contact ASED,
  or file a Maryland Public Information Act request.

## Consequences
- The pipeline must run offline from fixtures and snapshots; only `md-safety fetch` touches
  the network.
- Our data can lag the state's by up to a month. The site shows the refresh date and links
  to the official lookup.
- A change on the state's side can break the fetch. The count-drop gate in the build stops a
  bad refresh from deploying, and fixture-based tests show what changed.
