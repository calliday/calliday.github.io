#!/usr/bin/env python3
"""Check Megaplex Theatres showtimes for open luxury seats over the next few days.

Talks directly to Megaplex's public JSON API (apiv2.megaplex.com), which powers
megaplex.com. No API key or auth is required. See README.md for how the
endpoints were discovered and what they return.

By default, checks The Odyssey at Sandy at Jordan Commons.

Example:
    python3 check_luxury_seating.py
    python3 check_luxury_seating.py --days 3 --film "The Odyssey"
    python3 check_luxury_seating.py --film "" --days 5   # check every now-playing film instead
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

API_BASE = "https://apiv2.megaplex.com"
DEFAULT_CINEMA = "Sandy at Jordan Commons"
DEFAULT_FILM = "The Odyssey"
USER_AGENT = "Mozilla/5.0 (compatible; luxury-seat-checker/1.0)"
# Matches Jordan Commons' "Luxury" (heated recliner auditorium) and
# "Lux Box" (private box seating) session/area attributes.
LUXURY_RE = re.compile(r"luxury|lux box", re.IGNORECASE)


def _request(path, method="GET", body=None):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = resp.read().decode()
    result = json.loads(payload)
    # A couple of endpoints (e.g. seat-plan) return JSON double-encoded as a string.
    if isinstance(result, str):
        result = json.loads(result)
    return result


def find_cinema_id(name):
    for cinema in _request("/api/cinema/cinemas"):
        if cinema["name"].lower() == name.lower():
            return cinema["id"]
    raise SystemExit(f"Cinema {name!r} not found. Run with --list-cinemas to see valid names.")


def now_playing_for_cinema(cinema_id, film_filter=None):
    films = _request("/api/film/now-playing")
    films = [f for f in films if f["cinemaId"] == cinema_id]
    if film_filter:
        films = [f for f in films if film_filter.lower() in f["title"].lower()]
    return films


def sessions_for_film_on_date(scheduled_film_id, cinema_id, iso_date):
    data = _request(
        f"/api/film/film-with-sessions/{scheduled_film_id}",
        method="POST",
        body={"Date": iso_date, "CinemaIds": [cinema_id]},
    )
    sessions = []
    for cinema_sessions in data.get("cinemaSessions") or []:
        sessions.extend(cinema_sessions.get("sessions") or [])
    return sessions


def is_luxury_session(session):
    return any(LUXURY_RE.search(name) for name in session.get("sessionAttributesNames") or [])


def luxury_seat_availability(cinema_id, session_id):
    """Returns (available, total) luxury-area seats for a session, or None if unavailable."""
    numeric_id = session_id.split("-", 1)[-1]
    data = _request(f"/api/sessions/cinema/{cinema_id}/session/{numeric_id}/seat-plan")
    layout = data.get("SeatLayoutData")
    if not layout:
        return None
    total = available = 0
    for area in layout.get("Areas") or []:
        if not LUXURY_RE.search(area.get("Description") or ""):
            continue
        for row in area.get("Rows") or []:
            for seat in row.get("Seats") or []:
                total += 1
                if seat.get("Status") == 0:
                    available += 1
    return available, total


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=5, help="How many days ahead to check (default: 5)")
    parser.add_argument("--cinema", default=DEFAULT_CINEMA, help=f"Cinema name (default: {DEFAULT_CINEMA!r})")
    parser.add_argument(
        "--film",
        default=DEFAULT_FILM,
        help=f"Only check films whose title contains this text (default: {DEFAULT_FILM!r}; pass '' for all films)",
    )
    parser.add_argument("--delay", type=float, default=0.3, help="Seconds to sleep between API calls (default: 0.3)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of a table")
    parser.add_argument("--list-cinemas", action="store_true", help="List known cinema names and exit")
    args = parser.parse_args()

    if args.list_cinemas:
        for cinema in _request("/api/cinema/cinemas"):
            print(f"{cinema['id']}  {cinema['name']}")
        return

    cinema_id = find_cinema_id(args.cinema)
    films = now_playing_for_cinema(cinema_id, args.film)

    today = date.today()
    results = []
    for offset in range(args.days):
        iso_date = (today + timedelta(days=offset)).isoformat()
        for film in films:
            try:
                sessions = sessions_for_film_on_date(film["scheduledFilmId"], cinema_id, iso_date)
            except urllib.error.URLError as exc:
                print(f"warning: failed to fetch sessions for {film['title']} on {iso_date}: {exc}")
                continue
            time.sleep(args.delay)
            for session in sessions:
                if not is_luxury_session(session):
                    continue
                try:
                    availability = luxury_seat_availability(cinema_id, session["id"])
                except urllib.error.URLError as exc:
                    print(f"warning: failed to fetch seat plan for session {session['id']}: {exc}")
                    continue
                time.sleep(args.delay)
                if availability is None:
                    continue
                available, total = availability
                if available > 0:
                    results.append(
                        {
                            "date": iso_date,
                            "showtime": session["showtime"],
                            "film": film["title"],
                            "sessionId": session["id"],
                            "availableLuxurySeats": available,
                            "totalLuxurySeats": total,
                        }
                    )

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        scope = f" for {args.film!r}" if args.film else ""
        print(f"No open luxury seats found{scope} in the next {args.days} day(s) at {args.cinema}.")
        return

    results.sort(key=lambda r: r["showtime"])
    print(f"Open luxury seats at {args.cinema} (next {args.days} day(s)):\n")
    for r in results:
        print(f"  {r['showtime']}  {r['film']:<45}  {r['availableLuxurySeats']}/{r['totalLuxurySeats']} open")


if __name__ == "__main__":
    main()
