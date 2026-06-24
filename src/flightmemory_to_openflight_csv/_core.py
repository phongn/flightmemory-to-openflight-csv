"""Shared types, constants, and utilities for FlightMemory parsers."""

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import TypedDict

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


def make_flight(
    *,
    Date: str = "",
    From: str = "",
    To: str = "",
    Flight_Number: str = "",
    Airline: str = "",
    Distance: str = "",
    Duration: str = "",
    Seat: str = "",
    Seat_Type: str = "",
    Class: str = "",
    Reason: str = "",
    Plane: str = "",
    Registration: str = "",
    Note: str = "",
) -> Flight:
    """Build a Flight, defaulting the OpenFlights-assigned fields to empty.

    Trip and the four *_OID fields are populated by OpenFlights on import,
    so they are always written empty by this converter.
    """
    return Flight(
        Date=Date,
        From=From,
        To=To,
        Flight_Number=Flight_Number,
        Airline=Airline,
        Distance=Distance,
        Duration=Duration,
        Seat=Seat,
        Seat_Type=Seat_Type,
        Class=Class,
        Reason=Reason,
        Plane=Plane,
        Registration=Registration,
        Trip="",
        Note=Note,
        From_OID="",
        To_OID="",
        Airline_OID="",
        Plane_OID="",
    )


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
    s = s.strip()
    h, sep, m = s.partition(":")
    if not sep:
        return s
    try:
        return f"{int(h):02d}:{m}"
    except ValueError:
        return s  # non-numeric hour — pass through rather than crash


_MILES_PER_KM = 1.60934


def normalize_distance(value: str, unit: str) -> str:
    """Return the distance in miles. FlightMemory exports either mi or km."""
    value = value.replace(",", "")
    if unit == "km" and value:
        return str(round(float(value) / _MILES_PER_KM))
    return value


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
    all_ratings: dict[str, int] = {}
    if overall is not None:
        all_ratings["overall"] = overall
    all_ratings.update(ratings)
    if all_ratings:
        parts.append("[ratings: " + ", ".join(f"{k}={v}" for k, v in all_ratings.items()) + "]")
    return " ".join(parts)


def write_openflights_csv(flights: list[Flight], output: Path) -> None:
    """Write flights to an OpenFlights-compatible CSV file."""
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(flights)
