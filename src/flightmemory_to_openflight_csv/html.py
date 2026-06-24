"""Parse FlightMemory HTML exports into Flight records."""

from pathlib import Path

from bs4 import BeautifulSoup

from ._core import (
    CLASS_MAP,
    REASON_MAP,
    SEAT_TYPE_MAP,
    Flight,
    ParseIssue,
    ParseResult,
    RowParseError,
    UnsupportedFileError,
    _compose_note,
    _star_rating,
    is_recognised_date,
    make_flight,
    normalize_distance,
    parse_date,
    parse_duration,
    parse_time,
)


def _parse_seat_cell(cell) -> tuple[str, str, str, str]:
    """Return (seat, seat_type, cls, reason) from the seat/class cell."""
    seat = ""
    seat_type = ""
    cls = ""
    reason = ""

    small = cell.find("small")
    if small:
        # Collect direct text before the first <br> tag. Every child here
        # (NavigableString or Tag) exposes get_text().
        seat_raw = ""
        for child in cell.children:
            if getattr(child, "name", None) in ("br", "small"):
                break
            seat_raw += child.get_text()
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


def _parse_flight(main_cells, dist_cells, dur_cells) -> tuple[Flight, list[ParseIssue]]:
    """Parse one flight. Raise RowParseError if the row is unusable; otherwise
    return the flight and a list of non-fatal field-level issues."""
    issues: list[ParseIssue] = []

    nobr = main_cells[1].find("nobr")
    if not nobr:
        raise RowParseError("missing date cell")

    raw_date = nobr.get_text().strip()
    date = parse_date(raw_date)
    if not is_recognised_date(date):
        issues.append(ParseIssue("", f"unrecognised date {raw_date!r}; kept verbatim"))
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

    # Aircraft lines are positional: type, then optional registration, then
    # optional individual name. A name without a registration is unusual and
    # would be misread as the registration (the format carries no labels).
    plane_lines = [ln.strip() for ln in main_cells[7].get_text("\n").split("\n") if ln.strip()]
    plane = plane_lines[0] if plane_lines else ""
    registration = plane_lines[1] if len(plane_lines) > 1 else ""
    plane_name = plane_lines[2] if len(plane_lines) > 2 else ""

    seat, seat_type, cls, reason = _parse_seat_cell(main_cells[8])

    user_note_span = main_cells[9].find("span", title=True)
    user_note = user_note_span["title"] if user_note_span else ""

    overall = _star_rating(main_cells[0])
    ratings: dict[str, int] = {}
    for label, idx in (("dep_airport", 2), ("arr_airport", 4), ("airline", 6), ("airplane", 7)):
        r = _star_rating(main_cells[idx])
        if r is not None:
            ratings[label] = r

    distance = normalize_distance(
        dist_cells[0].get_text(strip=True), dist_cells[1].get_text(strip=True)
    )
    duration = parse_duration(dur_cells[0].get_text(strip=True))

    flight = make_flight(
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
        Note=_compose_note(user_note, plane_name, ratings, overall),
    )
    return flight, issues


def parse_html_file(path: Path) -> ParseResult:
    """Parse a FlightMemory HTML export.

    Raise UnsupportedFileError if the file contains no FlightMemory flight
    table. Individual rows that cannot be parsed are recorded as issues on the
    returned ParseResult rather than aborting the whole file.
    """
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    first_cell = soup.find("td", class_="liste_gross")
    if not first_cell:
        raise UnsupportedFileError(f"{path.name}: no FlightMemory flight table found")

    rows = first_cell.find_parent("table").find_all("tr")
    flights: list[Flight] = []
    issues: list[ParseIssue] = []
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
                no = cells[0].get_text(strip=True)
                location = f"flight {no}" if no else f"row {i}"
                try:
                    flight, row_issues = _parse_flight(cells, dist_cells, dur_cells)
                except RowParseError as e:
                    issues.append(ParseIssue(location, str(e)))
                except Exception as e:  # malformed row must not abort the file
                    issues.append(ParseIssue(location, f"unexpected error: {e}"))
                else:
                    flights.append(flight)
                    issues.extend(ParseIssue(location, ri.message) for ri in row_issues)
                i += 3
                continue
        i += 1

    return ParseResult(flights, issues)
