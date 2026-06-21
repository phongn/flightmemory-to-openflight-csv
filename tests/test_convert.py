"""Unit tests for flightmemory_to_openflight_csv.convert."""

import pytest
from bs4 import BeautifulSoup

from flightmemory_to_openflight_csv.convert import (
    _compose_note,
    _star_rating,
    parse_date,
    parse_duration,
    parse_seat_cell,
    parse_time,
)


def _td(html: str):
    """Wrap an HTML snippet in a <td> and return the BS4 element."""
    return BeautifulSoup(f"<td>{html}</td>", "html.parser").find("td")


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_mm_dd_yyyy(self):
        assert parse_date("12-31-2024") == "2024-12-31"

    def test_dd_mm_yyyy(self):
        assert parse_date("31.12.2024") == "2024-12-31"

    def test_dd_mm_yyyy_unambiguous(self):
        # Day > 12 makes the format unambiguous; ensure we don't swap month/day.
        assert parse_date("31.12.2017") == "2017-12-31"

    def test_year_only_recent(self):
        assert parse_date("2008") == "2008"

    def test_year_only_old(self):
        assert parse_date("1988") == "1988"

    def test_strips_whitespace(self):
        assert parse_date("  12-31-2024  ") == "2024-12-31"


# ---------------------------------------------------------------------------
# parse_duration
# ---------------------------------------------------------------------------

class TestParseDuration:
    def test_single_digit_hour(self):
        assert parse_duration("1:05") == "01:05"

    def test_double_digit_hour(self):
        assert parse_duration("14:25") == "14:25"

    def test_zero_hour(self):
        assert parse_duration("0:45") == "00:45"

    def test_no_colon_does_not_raise(self):
        # Malformed input should pass through rather than crashing the run.
        assert parse_duration("invalid") == "invalid"

    def test_strips_whitespace(self):
        assert parse_duration("  5:10  ") == "05:10"


# ---------------------------------------------------------------------------
# parse_time
# ---------------------------------------------------------------------------

class TestParseTime:
    def test_12h_am(self):
        assert parse_time("09:00 am") == "09:00"

    def test_12h_pm(self):
        assert parse_time("09:00 pm") == "21:00"

    def test_12h_am_late_morning(self):
        assert parse_time("10:30 am") == "10:30"

    def test_12h_noon(self):
        assert parse_time("12:00 pm") == "12:00"

    def test_12h_midnight(self):
        assert parse_time("12:00 am") == "00:00"

    def test_24h(self):
        assert parse_time("15:00") == "15:00"

    def test_24h_morning(self):
        assert parse_time("08:00") == "08:00"

    def test_empty_string(self):
        assert parse_time("") == ""

    def test_strips_whitespace(self):
        assert parse_time("  09:00 pm  ") == "21:00"


# ---------------------------------------------------------------------------
# parse_seat_cell
# ---------------------------------------------------------------------------

class TestParseSeatCell:
    def test_no_small_tag_returns_empty(self):
        td = _td(" / <br/>")
        assert parse_seat_cell(td) == ("", "", "", "")

    def test_three_line_small_no_seat(self):
        td = _td(' / <br/><small>EconomyPlus<br/>Passenger<br/>Personal</small>')
        seat, seat_type, cls, reason = parse_seat_cell(td)
        assert seat == ""
        assert seat_type == ""
        assert cls == "P"
        assert reason == "L"

    def test_three_line_small_with_seat_type(self):
        td = _td(' /Aisle<br/><small>EconomyPlus<br/>Passenger<br/>Personal</small>')
        seat, seat_type, cls, reason = parse_seat_cell(td)
        assert seat == ""
        assert seat_type == "A"
        assert cls == "P"
        assert reason == "L"

    def test_three_line_small_with_seat_number_and_type(self):
        td = _td('22B/Aisle<br/><small>EconomyPlus<br/>Passenger<br/>Personal</small>')
        seat, seat_type, cls, reason = parse_seat_cell(td)
        assert seat == "22B"
        assert seat_type == "A"
        assert cls == "P"
        assert reason == "L"

    def test_two_line_small_no_class(self):
        # Flights with no recorded seat class emit a leading <br/> inside
        # <small>, producing only two stripped lines: [PassengerType, Reason].
        # The reason must still be captured from the last line.
        td = _td(' / <br/><small><br/>Passenger<br/>Personal</small>')
        seat, seat_type, cls, reason = parse_seat_cell(td)
        assert cls == ""
        assert reason == "L"

    def test_business_class_and_reason(self):
        td = _td(' / <br/><small>Business<br/>Passenger<br/>Business</small>')
        _, __, cls, reason = parse_seat_cell(td)
        assert cls == "C"
        assert reason == "B"

    def test_first_class(self):
        td = _td(' / <br/><small>First<br/>Passenger<br/>Personal</small>')
        _, __, cls, ___ = parse_seat_cell(td)
        assert cls == "F"

    def test_economy_class(self):
        td = _td(' / <br/><small>Economy<br/>Passenger<br/>Personal</small>')
        _, __, cls, ___ = parse_seat_cell(td)
        assert cls == "Y"

    def test_window_seat_type(self):
        td = _td(' /Window<br/><small>Economy<br/>Passenger<br/>Personal</small>')
        _, seat_type, __, ___ = parse_seat_cell(td)
        assert seat_type == "W"

    def test_middle_seat_type(self):
        td = _td(' /Middle<br/><small>Economy<br/>Passenger<br/>Personal</small>')
        _, seat_type, __, ___ = parse_seat_cell(td)
        assert seat_type == "M"

    def test_unknown_reason_returns_empty(self):
        td = _td(' / <br/><small>Economy<br/>Passenger<br/>Unknown</small>')
        _, __, ___, reason = parse_seat_cell(td)
        assert reason == ""


# ---------------------------------------------------------------------------
# _star_rating
# ---------------------------------------------------------------------------

class TestStarRating:
    def test_star_1(self):
        td = _td('<img src="/images/star_1.gif" title="Rating: real bad"/>')
        assert _star_rating(td) == 1

    def test_star_5(self):
        td = _td('<img src="/images/star_5.gif" title="Rating: excellent"/>')
        assert _star_rating(td) == 5

    def test_no_image_returns_none(self):
        td = _td('<b>LAX</b>')
        assert _star_rating(td) is None

    def test_image_without_star_src_returns_none(self):
        td = _td('<img src="/images/dummy.gif"/>')
        assert _star_rating(td) is None


# ---------------------------------------------------------------------------
# _compose_note
# ---------------------------------------------------------------------------

class TestComposeNote:
    def test_all_empty(self):
        assert _compose_note("", "", {}) == ""

    def test_user_note_only(self):
        assert _compose_note("Example note.", "", {}) == "Example note."

    def test_plane_name_only(self):
        assert _compose_note("", "City of Nowhere", {}) == "[plane: City of Nowhere]"

    def test_ratings_only(self):
        result = _compose_note("", "", {"dep_airport": 5, "airline": 2})
        assert result == "[ratings: dep_airport=5, airline=2]"

    def test_overall_rating_only(self):
        assert _compose_note("", "", {}, overall=4) == "[ratings: overall=4]"

    def test_overall_rating_precedes_per_entity_ratings(self):
        result = _compose_note("", "", {"airline": 2}, overall=3)
        assert result == "[ratings: overall=3, airline=2]"

    def test_all_fields(self):
        result = _compose_note(
            "Example user note.",
            "City of Nowhere",
            {"dep_airport": 5, "arr_airport": 3, "airline": 2, "airplane": 1},
            overall=2,
        )
        assert result == (
            "Example user note. "
            "[plane: City of Nowhere] "
            "[ratings: overall=2, dep_airport=5, arr_airport=3, airline=2, airplane=1]"
        )
