# flightmemory-to-openflight-csv

Converts [FlightMemory](https://www.flightmemory.com/) flight-data exports — HTML or PDF — to the [OpenFlights](https://openflights.org/) personal flight log CSV format, ready for direct import.

## Requirements

Python 3.12 or later.

## Installation

```bash
pip install .                    # HTML support only
pip install ".[pdf]"             # HTML + PDF support
```

Or with uv:

```bash
uv sync                          # HTML support only
uv sync --extra pdf              # HTML + PDF support
```

## Exporting from FlightMemory

Log in and go to **Flight Data**, then export by either route:

- **HTML** (one file per page): **Save Page As → Webpage, HTML Only**, repeated for each page (FlightMemory paginates at 50 flights per page).
- **PDF** (one file, all flights): the **PDF File of FlightData** link.

Star ratings are only present in the HTML export, so prefer it if you want those captured (see [Field mapping](#field-mapping)).

## Usage

```bash
flightmemory-to-openflight-csv File1.html File2.html export.pdf ... -o flights.csv
```

HTML and PDF files can be mixed freely. All are merged and sorted by date (most recent first) before writing. File type is detected by extension.

| Argument | Default | Description |
|---|---|---|
| `FILE ...` | *(required)* | FlightMemory FlightData HTML exports and/or PDF exports |
| `-o / --output` | `flights.csv` | Output CSV path |

Each file is processed independently. An unreadable or unrecognised file is reported on stderr and skipped rather than aborting the run, and any per-record problems (e.g. an unrecognised date) are listed beneath that file's summary. The output CSV is **not** written when no flights parse at all, so a bad invocation never clobbers an existing file. The exit code is non-zero if any input failed.

## Library usage

The package is also a small library. The parsers return a `ParseResult` carrying the parsed flights and any non-fatal issues:

```python
from flightmemory_to_openflight_csv import (
    parse_html_file, parse_pdf_file, write_openflights_csv, UnsupportedFileError,
)

try:
    result = parse_html_file("FlightData 1.html")   # or parse_pdf_file(...)
except UnsupportedFileError as e:
    ...  # the file is not a FlightMemory export

for issue in result.issues:                          # non-fatal, per-record
    print(issue.location, issue.message)

write_openflights_csv(result.flights, "flights.csv")
```

| Name | Description |
|---|---|
| `parse_html_file(path) -> ParseResult` | Parse an HTML export; raises `UnsupportedFileError` if it has no flight table |
| `parse_pdf_file(path) -> ParseResult` | Parse a PDF export (needs the `pdf` extra); raises `UnsupportedFileError` if no rows are found |
| `ParseResult` | `.flights: list[Flight]`, `.issues: list[ParseIssue]`, `.ok: bool` |
| `ParseIssue` | `.location` (e.g. `"flight 239"`) and `.message` |
| `write_openflights_csv(flights, path)` | Write a list of `Flight` dicts as OpenFlights CSV |

Exceptions derive from `FlightMemoryError`: `UnsupportedFileError` (whole file unrecognised) and `RowParseError` (raised internally per row; surfaced as a `ParseIssue`).

## Format compatibility

| Detail | Value |
|---|---|
| [OpenFlights CSV](https://openflights.org/help/csv.php) revision targeted | 0.41 |
| FlightMemory export format tested | Site version as of 2026-06-21 |
| Output encoding | UTF-8 with BOM (as required by OpenFlights) |
| Output line endings | CRLF ([RFC 4180](https://datatracker.ietf.org/doc/html/rfc4180)) |

All three FlightMemory account display settings that affect the export are handled:

| Setting | Supported formats |
|---|---|
| Date | `MM-DD-YYYY`, `DD.MM.YYYY`, year-only `YYYY` (common for older flights) |
| Distance | Miles and km — km values are converted to miles on output |
| Time | 12-hour (`06:15 pm`) and 24-hour (`18:15`) — departure time is appended to the `Date` field when recorded |

## Field mapping

| OpenFlights field | FlightMemory source | Notes |
|---|---|---|
| `Date` | Date column (date + departure time) | Normalised to `YYYY-MM-DD [HH:MM]`; departure time appended when recorded |
| `From` | Departure IATA code | |
| `To` | Arrival IATA code | |
| `Flight_Number` | Airline column, second line | |
| `Airline` | Airline column, first line | |
| `Distance` | Distance column | Always output in miles |
| `Duration` | Duration column | Normalised to `HH:MM` |
| `Seat` | Seat column, text before `/` | |
| `Seat_Type` | Seat column, text after `/` | `Window`→`W`, `Aisle`→`A`, `Middle`→`M` |
| `Class` | First line of seat details block | `First`→`F`, `Business`→`C`, `EconomyPlus`→`P`, `Economy`→`Y` |
| `Reason` | Last line of seat details block | `Personal`→`L`, `Business`→`B`, `Crew`→`C`, `Virtuell`→`O` |
| `Plane` | Aircraft column, first line | |
| `Registration` | Aircraft column, second line | When recorded |
| `Note` | User comment, plane name, star ratings | Comment verbatim, then `[plane: …]` and `[ratings: overall=N, …]` for data OpenFlights has no field for |
| `Trip`, `*_OID` | — | Left empty; assigned by OpenFlights on import |

## Development

```bash
pip install ".[dev,pdf]"
pytest
```

Or with uv:

```bash
uv sync --extra dev --extra pdf
uv run pytest
```

## Authors

- Phong Nguyen
- [Claude Sonnet 4.6](https://www.anthropic.com) (Anthropic)
