"""Parse FlightMemory PDF exports into Flight records."""

from __future__ import annotations

import sys
from pathlib import Path

from .convert import (
    CLASS_MAP,
    REASON_MAP,
    SEAT_TYPE_MAP,
    Flight,
    _compose_note,
    parse_date,
    parse_duration,
    parse_time,
)

try:
    import pdfplumber as _pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

# x0 column boundaries calibrated against observed data word positions.
# Header labels sit 0–1 pt to the right of the leftmost data words they
# head, so boundaries are set from the data, not the header labels.
# Each entry is (lo_inclusive, hi_exclusive).
_COLS: dict[str, tuple[float, float]] = {
    "no":       (0,     31),
    "date":     (31,    79),
    "dep_iata": (79,   102),
    "dep_det":  (102,  164),
    "arr_iata": (164,  187),
    "arr_det":  (187,  249),
    "distance": (249,  288),    # distance on line 1, duration on line 2
    "airline":  (288,  359),    # airline name on line 1, flight number on line 2
    "airplane": (359,  442),    # type / registration / plane name / reason
    "seat":     (442,  487),    # seat number / type / class / pax role
    "comment":  (487,  9999),
}

_HEADER_MIN_TOP = 120   # data rows start below this y-coordinate
_PAGE_FOOTER_TOP = 800  # ignore footer below this y-coordinate
_LINE_TOL = 3.0         # pt tolerance for grouping words into one line

_KNOWN_PAX_ROLES = {"passenger", "crew", "cockpit"}


def _col_words(words: list[dict], col: str) -> list[dict]:
    lo, hi = _COLS[col]
    return [w for w in words if lo <= w["x0"] < hi]


def _group_lines(words: list[dict]) -> list[str]:
    """Group words into text lines by vertical proximity; return ordered strings."""
    if not words:
        return []
    words = sorted(words, key=lambda w: w["top"])
    lines: list[list[dict]] = [[words[0]]]
    for w in words[1:]:
        if abs(w["top"] - lines[-1][0]["top"]) <= _LINE_TOL:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [
        " ".join(x["text"] for x in sorted(line, key=lambda x: x["x0"]))
        for line in lines
    ]


def _lines(row_words: list[dict], col: str) -> list[str]:
    return _group_lines(_col_words(row_words, col))


def _parse_airplane(lines: list[str]) -> tuple[str, str, str, str]:
    """Return (plane, registration, plane_name, reason) from Airplane column lines."""
    if not lines:
        return ("", "", "", "")
    plane = lines[0]
    remaining = list(lines[1:])

    # Reason is the last line when it matches a known keyword.
    reason = ""
    if remaining and remaining[-1].lower() in REASON_MAP:
        reason = REASON_MAP[remaining[-1].lower()]
        remaining = remaining[:-1]

    registration = remaining[0] if remaining else ""
    plane_name = " ".join(remaining[1:]) if len(remaining) > 1 else ""
    return plane, registration, plane_name, reason


def _parse_seat(lines: list[str]) -> tuple[str, str, str]:
    """Return (seat_number, seat_type, cls) from Seat column lines."""
    seat = ""
    seat_type = ""
    cls = ""
    for line in lines:
        low = line.lower()
        if low in SEAT_TYPE_MAP:
            seat_type = SEAT_TYPE_MAP[low]
        elif low in CLASS_MAP:
            cls = CLASS_MAP[low]
        elif low in _KNOWN_PAX_ROLES:
            pass  # passenger role — no OpenFlights field
        else:
            seat = line  # seat number (e.g. "3A")
    return seat, seat_type, cls


def _parse_pdf_row(row_words: list[dict]) -> Flight | None:
    # Date and optional departure time
    date_ln = _lines(row_words, "date")
    if not date_ln:
        return None
    date = parse_date(date_ln[0])
    if len(date_ln) > 1:
        dep_time = parse_time(date_ln[1])
        if dep_time:
            date = f"{date} {dep_time}"
    # date_ln[2] is arrival time (ignored — OpenFlights derives it from Date+Duration)

    dep = next(iter(_lines(row_words, "dep_iata")), "")
    arr = next(iter(_lines(row_words, "arr_iata")), "")

    # Distance column holds distance on line 1, duration on line 2
    dist_ln = _lines(row_words, "distance")
    distance = ""
    duration = ""
    if dist_ln:
        parts = dist_ln[0].split()
        dist_val = parts[0].replace(",", "") if parts else ""
        dist_unit = parts[1] if len(parts) > 1 else "mi"
        if dist_unit == "km" and dist_val:
            distance = str(round(float(dist_val) / 1.60934))
        else:
            distance = dist_val
    if len(dist_ln) > 1:
        dur_parts = dist_ln[1].split()
        if dur_parts:
            duration = parse_duration(dur_parts[0])

    airline_ln = _lines(row_words, "airline")
    airline = airline_ln[0] if airline_ln else ""
    flight_number = airline_ln[1] if len(airline_ln) > 1 else ""

    plane, registration, plane_name, reason = _parse_airplane(_lines(row_words, "airplane"))
    seat, seat_type, cls = _parse_seat(_lines(row_words, "seat"))

    user_note = " ".join(_lines(row_words, "comment"))

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
        Note=_compose_note(user_note, plane_name, {}, None),
        From_OID="",
        To_OID="",
        Airline_OID="",
        Plane_OID="",
    )


def parse_pdf_file(path: Path) -> list[Flight]:
    """Parse a FlightMemory PDF export and return a list of Flight records.

    Requires the ``pdf`` optional dependency:
    ``pip install 'flightmemory-to-openflight-csv[pdf]'``
    """
    if not _HAS_PDFPLUMBER:
        raise ImportError(
            "pdfplumber is required for PDF parsing. "
            "Install it with: pip install 'flightmemory-to-openflight-csv[pdf]'"
        )

    flights: list[Flight] = []
    no_col_lo, no_col_hi = _COLS["no"]

    with _pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=1)
            data_words = [
                w for w in words
                if _HEADER_MIN_TOP < w["top"] < _PAGE_FOOTER_TOP
            ]

            # Row starts are words in the No. column that are purely numeric.
            row_tops = [
                w["top"] for w in data_words
                if no_col_lo <= w["x0"] < no_col_hi and w["text"].isdigit()
            ]
            if not row_tops:
                continue

            # Pair each row start with the next to bound the word block.
            row_tops_sentinel = row_tops + [_PAGE_FOOTER_TOP]
            for start, end in zip(row_tops_sentinel, row_tops_sentinel[1:]):
                row_words = [
                    w for w in data_words if start - 1 <= w["top"] < end - 1
                ]
                flight = _parse_pdf_row(row_words)
                if flight:
                    flights.append(flight)

    print(f"{path.name}: {len(flights)} flights", file=sys.stderr)
    return flights
