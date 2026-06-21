"""Convert FlightMemory HTML exports to OpenFlights CSV format."""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from bs4 import BeautifulSoup

FIELDNAMES = [
    "Date", "From", "To", "Flight_Number", "Airline", "Distance", "Duration",
    "Seat", "Seat_Type", "Class", "Reason", "Plane", "Registration",
    "Trip", "Note", "From_OID", "To_OID", "Airline_OID", "Plane_OID",
]

CLASS_MAP = {
    "first": "F",
    "business": "C",
    "economyplus": "P",
    "premium economy": "P",
    "economy": "Y",
}

SEAT_TYPE_MAP = {
    "window": "W",
    "aisle": "A",
    "middle": "M",
}

REASON_MAP = {
    "personal": "L",
    "business": "B",
    "crew": "C",
    "virtuell": "O",  # simulator/virtual flight
}

_STAR_RE = re.compile(r"/star_(\d)\.gif")


class Flight(TypedDict):
    Date: str
    From: str
    To: str
    Flight_Number: str
    Airline: str
    Distance: str
    Duration: str
    Seat: str
    Seat_Type: str
    Class: str
    Reason: str
    Plane: str
    Registration: str
    Trip: str
    Note: str
    From_OID: str
    To_OID: str
    Airline_OID: str
    Plane_OID: str


def _star_rating(cell) -> int | None:
    """Return the star rating (1–5) from the first <img> in a cell, or None."""
    img = cell.find("img")
    if img:
        m = _STAR_RE.search(img.get("src", ""))
        if m:
            return int(m.group(1))
    return None


def parse_date(s: str) -> str:
    s = s.strip()
    for fmt in ("%m-%d-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s  # year-only ("YYYY") — OpenFlights accepts this format


def parse_time(s: str) -> str:
    """Normalise a 12- or 24-hour time string to HH:MM."""
    s = s.strip()
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return ""


def parse_duration(s: str) -> str:
    h, sep, m = s.strip().partition(":")
    if not sep:
        return s.strip()
    return f"{int(h):02d}:{m}"


def parse_seat_cell(cell) -> tuple[str, str, str, str]:
    """Return (seat, seat_type, cls, reason) from the seat/class cell."""
    seat = ""
    seat_type = ""
    cls = ""
    reason = ""

    small = cell.find("small")
    if small:
        # Collect direct text before the first <br> tag
        seat_raw = ""
        for child in cell.children:
            if getattr(child, "name", None) in ("br", "small"):
                break
            seat_raw += child.get_text() if hasattr(child, "get_text") else str(child)
        seat_raw = seat_raw.strip()

        if "/" in seat_raw:
            left, right = seat_raw.split("/", 1)
            seat = left.strip()
            seat_type = SEAT_TYPE_MAP.get(right.strip().lower(), "")

        lines = [ln.strip() for ln in small.get_text("\n").split("\n") if ln.strip()]
        if lines:
            cls = CLASS_MAP.get(lines[0].lower(), "")
        if len(lines) >= 2:
            # Reason is always the last line; structure is either
            # [Class, PassengerType, Reason] or [PassengerType, Reason]
            reason = REASON_MAP.get(lines[-1].lower(), "")

    return seat, seat_type, cls, reason


def _compose_note(
    user_note: str,
    plane_name: str,
    ratings: dict[str, int],
    overall: int | None = None,
) -> str:
    """Compose the OpenFlights Note field from available metadata."""
    parts = []
    if user_note:
        parts.append(user_note)
    if plane_name:
        parts.append(f"[plane: {plane_name}]")
    all_ratings = {}
    if overall is not None:
        all_ratings["overall"] = overall
    all_ratings.update(ratings)
    if all_ratings:
        parts.append("[ratings: " + ", ".join(f"{k}={v}" for k, v in all_ratings.items()) + "]")
    return " ".join(parts)


def parse_flight(main_cells, dist_cells, dur_cells) -> Flight | None:
    nobr = main_cells[1].find("nobr")
    if not nobr:
        return None

    date = parse_date(nobr.get_text())
    time_texts = [
        str(c).strip() for c in main_cells[1].children
        if getattr(c, "name", None) not in ("nobr", "br") and str(c).strip()
    ]
    if time_texts:
        dep_time = parse_time(time_texts[0])
        if dep_time:
            date = f"{date} {dep_time}"

    dep_b = main_cells[2].find("b")
    dep = dep_b.get_text(strip=True) if dep_b else ""
    arr_b = main_cells[4].find("b")
    arr = arr_b.get_text(strip=True) if arr_b else ""

    airline_lines = [ln.strip() for ln in main_cells[6].get_text("\n").split("\n") if ln.strip()]
    airline = airline_lines[0] if airline_lines else ""
    flight_number = airline_lines[1] if len(airline_lines) > 1 else ""

    plane_lines = [ln.strip() for ln in main_cells[7].get_text("\n").split("\n") if ln.strip()]
    plane = plane_lines[0] if plane_lines else ""
    registration = plane_lines[1] if len(plane_lines) > 1 else ""
    plane_name = plane_lines[2] if len(plane_lines) > 2 else ""

    seat, seat_type, cls, reason = parse_seat_cell(main_cells[8])

    user_note_span = main_cells[9].find("span", title=True)
    user_note = user_note_span["title"] if user_note_span else ""

    overall = _star_rating(main_cells[0])
    ratings: dict[str, int] = {}
    for label, idx in (("dep_airport", 2), ("arr_airport", 4), ("airline", 6), ("airplane", 7)):
        r = _star_rating(main_cells[idx])
        if r is not None:
            ratings[label] = r

    distance_raw = dist_cells[0].get_text(strip=True).replace(",", "")
    dist_unit = dist_cells[1].get_text(strip=True)
    if dist_unit == "km" and distance_raw:
        distance = str(round(float(distance_raw) / 1.60934))
    else:
        distance = distance_raw
    duration = parse_duration(dur_cells[0].get_text(strip=True))

    return Flight(
        Date=date,
        From=dep,
        To=arr,
        Flight_Number=flight_number,
        Airline=airline,
        Distance=distance,
        Duration=duration,
        Seat=seat,
        Seat_Type=seat_type,
        Class=cls,
        Reason=reason,
        Plane=plane,
        Registration=registration,
        Trip="",
        Note=_compose_note(user_note, plane_name, ratings, overall),
        From_OID="",
        To_OID="",
        Airline_OID="",
        Plane_OID="",
    )


def parse_html_file(path: Path) -> list[Flight]:
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    first_cell = soup.find("td", class_="liste_gross")
    if not first_cell:
        print(f"Warning: {path.name}: no flight table found — wrong file?", file=sys.stderr)
        return []

    rows = first_cell.find_parent("table").find_all("tr")
    flights: list[Flight] = []
    i = 0
    while i < len(rows):
        cells = rows[i].find_all("td", recursive=False)
        if (
            len(cells) == 10
            and cells[0].get("class") == ["liste_gross"]
            and i + 2 < len(rows)
        ):
            dist_cells = rows[i + 1].find_all("td", recursive=False)
            dur_cells = rows[i + 2].find_all("td", recursive=False)
            if len(dist_cells) == 2 and len(dur_cells) == 2:
                flight = parse_flight(cells, dist_cells, dur_cells)
                if flight:
                    flights.append(flight)
                i += 3
                continue
        i += 1

    return flights


def write_openflights_csv(flights: list[Flight], output: Path) -> None:
    """Write flights to an OpenFlights-compatible CSV file."""
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(flights)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert FlightMemory HTML exports to OpenFlights CSV."
    )
    parser.add_argument("html_files", nargs="+", type=Path, metavar="HTML_FILE")
    parser.add_argument("-o", "--output", type=Path, default=Path("flights.csv"))
    args = parser.parse_args()

    all_flights: list[Flight] = []
    for path in args.html_files:
        flights = parse_html_file(path)
        print(f"{path.name}: {len(flights)} flights", file=sys.stderr)
        all_flights.extend(flights)

    all_flights.sort(key=lambda f: f["Date"], reverse=True)
    write_openflights_csv(all_flights, args.output)
    print(f"Wrote {len(all_flights)} flights to {args.output}", file=sys.stderr)
