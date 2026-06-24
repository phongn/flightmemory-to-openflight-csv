"""Unit tests for the flightmemory_to_openflight_csv library."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from flightmemory_to_openflight_csv import (
    RowParseError,
    UnsupportedFileError,
    parse_html_file,
)
from flightmemory_to_openflight_csv._core import (
    _compose_note,
    _star_rating,
    is_recognised_date,
    normalize_distance,
    parse_date,
    parse_duration,
    parse_time,
)
from flightmemory_to_openflight_csv.html import _parse_seat_cell
from flightmemory_to_openflight_csv.pdf import _parse_airplane, _parse_pdf_row, _parse_seat

FIXTURES = Path(__file__).parent / "fixtures"


def _td(html: str):
    """Wrap an HTML snippet in a <td> and return the BS4 element."""
    return BeautifulSoup(f"<td>{html}</td>", "html.parser").find("td")


def _word(text: str, x0: float, top: float) -> dict:
    """Build a pdfplumber-style word dict (only the keys the parser reads)."""
    return {"text": text, "x0": x0, "top": top}


# A minimal single-flight table (No. 1) used by error-path tests that mutate
# one field; the parser locates it via the first td.liste_gross cell.
_ONE_FLIGHT_TEMPLATE = """<table>
<tr valign="top">
  <td align="right" class="liste_gross">1<br/></td>
  <td class="liste"><nobr>12-31-2024</nobr><br/><br/> </td>
  <td class="liste_gross"><b>AAA</b><br/></td>
  <td class="liste"><b>Alphaville</b><br/>Wonderland<br/>Alpha International</td>
  <td class="liste_gross"><b>BBB</b><br/></td>
  <td class="liste"><b>Betatown</b><br/>Wonderland<br/>Beta Field</td>
  <td class="liste">Test Air<br/>123</td>
  <td class="liste">Boeing 737</td>
  <td class="liste">12A/Window<br/><small>Economy<br/>Passenger<br/>Personal</small></td>
  <td class="liste"><br/><select><option value="NIL">Flight</option></select></td>
</tr>
<tr valign="top"><td align="right">100 </td><td>mi</td></tr>
<tr valign="top"><td align="right">1:00 </td><td>h</td></tr>
</table>"""


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

    def test_non_numeric_hour_does_not_raise(self):
        # A colon with a non-numeric hour must not crash the int() conversion.
        assert parse_duration("ab:cd") == "ab:cd"

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
# _parse_seat_cell
# ---------------------------------------------------------------------------

class TestParseSeatCell:
    def test_no_small_tag_returns_empty(self):
        td = _td(" / <br/>")
        assert _parse_seat_cell(td) == ("", "", "", "")

    def test_three_line_small_no_seat(self):
        td = _td(' / <br/><small>EconomyPlus<br/>Passenger<br/>Personal</small>')
        seat, seat_type, cls, reason = _parse_seat_cell(td)
        assert seat == ""
        assert seat_type == ""
        assert cls == "P"
        assert reason == "L"

    def test_three_line_small_with_seat_type(self):
        td = _td(' /Aisle<br/><small>EconomyPlus<br/>Passenger<br/>Personal</small>')
        seat, seat_type, cls, reason = _parse_seat_cell(td)
        assert seat == ""
        assert seat_type == "A"
        assert cls == "P"
        assert reason == "L"

    def test_three_line_small_with_seat_number_and_type(self):
        td = _td('22B/Aisle<br/><small>EconomyPlus<br/>Passenger<br/>Personal</small>')
        seat, seat_type, cls, reason = _parse_seat_cell(td)
        assert seat == "22B"
        assert seat_type == "A"
        assert cls == "P"
        assert reason == "L"

    def test_two_line_small_no_class(self):
        # Flights with no recorded seat class emit a leading <br/> inside
        # <small>, producing only two stripped lines: [PassengerType, Reason].
        # The reason must still be captured from the last line.
        td = _td(' / <br/><small><br/>Passenger<br/>Personal</small>')
        seat, seat_type, cls, reason = _parse_seat_cell(td)
        assert cls == ""
        assert reason == "L"

    def test_business_class_and_reason(self):
        td = _td(' / <br/><small>Business<br/>Passenger<br/>Business</small>')
        _, __, cls, reason = _parse_seat_cell(td)
        assert cls == "C"
        assert reason == "B"

    def test_first_class(self):
        td = _td(' / <br/><small>First<br/>Passenger<br/>Personal</small>')
        _, __, cls, ___ = _parse_seat_cell(td)
        assert cls == "F"

    def test_economy_class(self):
        td = _td(' / <br/><small>Economy<br/>Passenger<br/>Personal</small>')
        _, __, cls, ___ = _parse_seat_cell(td)
        assert cls == "Y"

    def test_window_seat_type(self):
        td = _td(' /Window<br/><small>Economy<br/>Passenger<br/>Personal</small>')
        _, seat_type, __, ___ = _parse_seat_cell(td)
        assert seat_type == "W"

    def test_middle_seat_type(self):
        td = _td(' /Middle<br/><small>Economy<br/>Passenger<br/>Personal</small>')
        _, seat_type, __, ___ = _parse_seat_cell(td)
        assert seat_type == "M"

    def test_unknown_reason_returns_empty(self):
        td = _td(' / <br/><small>Economy<br/>Passenger<br/>Unknown</small>')
        _, __, ___, reason = _parse_seat_cell(td)
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


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

class TestParsePdfAirplane:
    def test_type_only(self):
        plane, reg, name, reason = _parse_airplane(["Boeing 727"])
        assert plane == "Boeing 727"
        assert reg == ""
        assert name == ""
        assert reason == ""

    def test_type_and_reason(self):
        plane, reg, name, reason = _parse_airplane(["Boeing 727", "Personal"])
        assert plane == "Boeing 727"
        assert reg == ""
        assert reason == "L"

    def test_type_reg_reason(self):
        plane, reg, name, reason = _parse_airplane(["Airbus 321", "N985JT", "Personal"])
        assert plane == "Airbus 321"
        assert reg == "N985JT"
        assert name == ""
        assert reason == "L"

    def test_type_reg_name_reason(self):
        plane, reg, name, reason = _parse_airplane(
            ["Airbus 321", "N985JT", "City of Nowhere", "Personal"]
        )
        assert plane == "Airbus 321"
        assert reg == "N985JT"
        assert name == "City of Nowhere"
        assert reason == "L"

    def test_empty(self):
        assert _parse_airplane([]) == ("", "", "", "")

    def test_virtual_reason(self):
        _, __, ___, reason = _parse_airplane(["Boeing 737", "Virtuell"])
        assert reason == "O"


class TestParsePdfSeat:
    def test_empty(self):
        assert _parse_seat([]) == ("", "", "")

    def test_pax_role_only(self):
        seat, seat_type, cls = _parse_seat(["Passenger"])
        assert seat == ""
        assert seat_type == ""
        assert cls == ""

    def test_class_and_pax(self):
        seat, seat_type, cls = _parse_seat(["Business", "Passenger"])
        assert cls == "C"
        assert seat == ""

    def test_seat_number_type_class_pax(self):
        seat, seat_type, cls = _parse_seat(["22B", "Window", "Business", "Passenger"])
        assert seat == "22B"
        assert seat_type == "W"
        assert cls == "C"


# ---------------------------------------------------------------------------
# normalize_distance
# ---------------------------------------------------------------------------

class TestNormalizeDistance:
    def test_miles_passthrough(self):
        assert normalize_distance("308", "mi") == "308"

    def test_strips_thousands_comma(self):
        assert normalize_distance("2,583", "mi") == "2583"

    def test_km_to_miles(self):
        assert normalize_distance("4157", "km") == "2583"

    def test_empty_value(self):
        assert normalize_distance("", "km") == ""


# ---------------------------------------------------------------------------
# parse_html_file (end-to-end against a fixture)
# ---------------------------------------------------------------------------

class TestParseHtmlFile:
    def test_returns_both_flights_in_document_order(self):
        result = parse_html_file(FIXTURES / "sample_flightdata.html")
        assert [f["From"] for f in result.flights] == ["AAA", "CCC"]

    def test_clean_file_has_no_issues(self):
        result = parse_html_file(FIXTURES / "sample_flightdata.html")
        assert result.ok
        assert result.issues == []

    def test_fully_populated_flight(self):
        result = parse_html_file(FIXTURES / "sample_flightdata.html")
        assert result.flights[0] == {
            "Date": "2024-12-31 09:00",
            "From": "AAA",
            "To": "BBB",
            "Flight_Number": "123",
            "Airline": "Test Air",
            "Distance": "1000",
            "Duration": "02:30",
            "Seat": "12A",
            "Seat_Type": "W",
            "Class": "C",
            "Reason": "L",
            "Plane": "Boeing 737",
            "Registration": "N12345",
            "Trip": "",
            "Note": (
                "Great flight. [plane: Spirit of Testing] "
                "[ratings: overall=3, dep_airport=5, arr_airport=4, airline=2, airplane=1]"
            ),
            "From_OID": "",
            "To_OID": "",
            "Airline_OID": "",
            "Plane_OID": "",
        }

    def test_sparse_flight_year_only_date_and_km(self):
        result = parse_html_file(FIXTURES / "sample_flightdata.html")
        f = result.flights[1]
        assert f["Date"] == "2010"          # year-only, passed through
        assert f["Airline"] == "Budget Wings"
        assert f["Flight_Number"] == ""
        assert f["Distance"] == "311"        # 500 km → miles
        assert f["Duration"] == "01:00"
        assert f["Reason"] == "L"            # 2-line <small>, reason on last line
        assert f["Class"] == ""
        assert f["Plane"] == ""
        assert f["Note"] == ""

    def test_accepts_str_path(self):
        result = parse_html_file(str(FIXTURES / "sample_flightdata.html"))
        assert len(result.flights) == 2

    def test_non_flightmemory_file_raises(self, tmp_path):
        wrong = tmp_path / "notflightmemory.html"
        wrong.write_text("<html><body><p>not a flight log</p></body></html>")
        with pytest.raises(UnsupportedFileError):
            parse_html_file(wrong)

    def test_unrecognised_date_is_reported_but_flight_kept(self, tmp_path):
        html = _ONE_FLIGHT_TEMPLATE.replace("<nobr>12-31-2024</nobr>", "<nobr>sometime</nobr>")
        path = tmp_path / "baddate.html"
        path.write_text(html)
        result = parse_html_file(path)
        assert len(result.flights) == 1            # row kept
        assert result.flights[0]["Date"] == "sometime"
        assert not result.ok
        assert "unrecognised date" in result.issues[0].message
        assert result.issues[0].location == "flight 1"


# ---------------------------------------------------------------------------
# _parse_pdf_row (synthetic words at the documented column x0 ranges)
# ---------------------------------------------------------------------------

class TestParsePdfRow:
    def _fully_populated_words(self) -> list[dict]:
        # One flight laid out across four text lines (top 100/110/120/130),
        # with each word's x0 inside its documented column boundary.
        return [
            _word("42", 15, 100),
            _word("12-31-2023", 31, 100), _word("10:24", 31, 110), _word("pm", 53, 110),
            _word("06:48", 31, 120), _word("am", 53, 120), _word("+1", 67, 120),
            _word("AAA", 79, 100),
            _word("Alphaville", 102, 100), _word("Alpha", 102, 120), _word("International", 120, 120),
            _word("BBB", 164, 100),
            _word("Betatown", 187, 100),
            _word("2,000", 251, 100), _word("mi", 274, 100),
            _word("5:24", 260, 110), _word("h", 278, 110),
            _word("Test", 288, 100), _word("Air", 310, 100), _word("456", 289, 110),
            _word("Airbus", 359, 100), _word("321", 384, 100),
            _word("N99999", 359, 110),
            _word("Spirit", 359, 120), _word("of", 380, 120), _word("Testing", 395, 120),
            _word("Personal", 359, 130),
            _word("3A", 442, 100), _word("Window", 442, 110),
            _word("Business", 442, 120), _word("Passenger", 442, 130),
            _word("Broken", 487, 100), _word("seat.", 511, 100),
        ]

    def test_fully_populated_row(self):
        flight, issues = _parse_pdf_row(self._fully_populated_words())
        assert issues == []
        assert flight == {
            "Date": "2023-12-31 22:24",
            "From": "AAA",
            "To": "BBB",
            "Flight_Number": "456",
            "Airline": "Test Air",
            "Distance": "2000",
            "Duration": "05:24",
            "Seat": "3A",
            "Seat_Type": "W",
            "Class": "C",
            "Reason": "L",
            "Plane": "Airbus 321",
            "Registration": "N99999",
            "Trip": "",
            "Note": "Broken seat. [plane: Spirit of Testing]",
            "From_OID": "",
            "To_OID": "",
            "Airline_OID": "",
            "Plane_OID": "",
        }

    def test_km_distance_converted(self):
        words = [
            _word("1", 15, 100),
            _word("2015", 31, 100),
            _word("1,000", 251, 100), _word("km", 274, 100),
        ]
        flight, _ = _parse_pdf_row(words)
        assert flight["Date"] == "2015"
        assert flight["Distance"] == "621"   # 1000 km → miles

    def test_no_date_raises(self):
        with pytest.raises(RowParseError):
            _parse_pdf_row([_word("42", 15, 100)])


# ---------------------------------------------------------------------------
# is_recognised_date
# ---------------------------------------------------------------------------

class TestIsRecognisedDate:
    def test_full_date(self):
        assert is_recognised_date("2024-12-31")

    def test_year_only(self):
        assert is_recognised_date("1988")

    def test_garbage(self):
        assert not is_recognised_date("sometime")

    def test_partial(self):
        assert not is_recognised_date("2024-12")
