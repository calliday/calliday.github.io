# Megaplex Luxury Seating Checker

A script to check whether luxury seats (heated recliners / "Lux Box" seating)
are open for upcoming showtimes at a Megaplex Theatres location — by default,
**Sandy at Jordan Commons**.

## Is the Megaplex API scrapable?

Yes. `megaplex.com` is an Angular SPA whose backend, `apiv2.megaplex.com`
(built on the Vista Cinema platform), is a **plain, unauthenticated JSON REST
API** — no API key, login, or session cookie required. It responds cleanly to
direct `curl`/`urllib` requests with a normal browser `User-Agent`.

Two caveats found during discovery:

- The **marketing site** (`megaplex.com`'s individual `/locations/...` pages)
  sits behind Incapsula bot-protection and returns a JS challenge page to
  plain HTTP clients. The **API host** (`apiv2.megaplex.com`) does not have
  this in front of it — it's a normal server API meant to be called from the
  Angular app's browser JS, and responds directly.
- Endpoints were found by downloading the site's Angular JS bundles
  (`main-*.js`, `chunk-*.js`) and grepping them for `API_V2_URL` and
  `/api/...` string literals — there's no public API documentation.

### Endpoints used

| Purpose | Method | Path |
|---|---|---|
| List cinemas (find a location's `cinemaId`) | `GET` | `/api/cinema/cinemas` |
| Now-playing films (all cinemas, filter client-side by `cinemaId`) | `GET` | `/api/film/now-playing` |
| Showtimes for a film, cinema, and date | `POST` | `/api/film/film-with-sessions/{scheduledFilmId}` body `{"Date": "YYYY-MM-DD", "CinemaIds": ["0001"]}` |
| Full seat map for a specific showtime | `GET` | `/api/sessions/cinema/{cinemaId}/session/{sessionId}/seat-plan` |

Notes on the data:

- `cinemaId` for Sandy at Jordan Commons is `"0001"`.
- Session IDs come back like `"0001-253613"` (`cinemaId-sessionId`), but the
  seat-plan endpoint wants just the numeric part (`253613`).
- Each session has a `sessionAttributesNames` list (e.g. `["2D", "Luxury",
  "CC", "DVS"]`). Jordan Commons has "heated luxury seating" throughout (per
  its own theatre description), so most/all of its sessions carry a
  `"Luxury"` attribute; some also carry `"Lux Box"` for private box seating.
- The seat-plan response's `SeatLayoutData.Areas[]` breaks the auditorium
  into named areas (e.g. `"Luxury"`, `"Exit"`). Each seat has a numeric
  `Status`; `0` means the seat is open/unsold, any other value seen so far
  (`3`, `7`, ...) corresponds to sold/held/companion seats. This script
  treats `Status == 0` as "available."

## Usage

No third-party dependencies — just Python 3's standard library.

```bash
# Check all now-playing films at Jordan Commons for open luxury seats
# over the next 5 days (default)
python3 check_luxury_seating.py

# Narrow to one movie and a shorter window
python3 check_luxury_seating.py --film "Super Troopers 3" --days 3

# Check a different Megaplex location
python3 check_luxury_seating.py --list-cinemas
python3 check_luxury_seating.py --cinema "Salt Lake City at The Gateway"

# Machine-readable output (for wiring into another tool/notifier)
python3 check_luxury_seating.py --json
```

The script prints any showtime in the window with at least one open luxury
seat, along with how many are open out of the section's total.

Checking every now-playing film over several days means dozens of API calls;
a `--delay` flag (default `0.3`s between requests) keeps it polite to
Megaplex's API. Narrowing with `--film` cuts this down a lot.
