# flightmemory-to-openflight-csv

Converts [FlightMemory](https://www.flightmemory.com/) HTML flight-data exports to the [OpenFlights](https://openflights.org/) personal flight log CSV format, ready for direct import.

## Requirements

Python 3.12 or later.

## Installation

```bash
pip install .
```

Or, if you prefer [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

## Exporting from FlightMemory

1. Log in and go to **Flight Data**.
2. Use **Save Page As → Webpage, HTML Only** for each page of results.
3. Repeat for all pages (FlightMemory paginates at 50 flights per page).

## Usage

```bash
flightmemory-to-openflight-csv Page1.html Page2.html ... -o flights.csv
```

All pages are merged and sorted by date (most recent first) before writing.

| Argument | Default | Description |
|---|---|---|
| `HTML_FILE ...` | *(required)* | One or more FlightMemory FlightData HTML exports |
| `-o / --output` | `flights.csv` | Output CSV path |

## Format compatibility

| Detail | Value |
|---|---|
| OpenFlights CSV revision targeted | 0.41 |
| FlightMemory export format tested | Site version as of 2026-06-21 |
| Output encoding | UTF-8 with BOM (as required by OpenFlights) |
| Output line endings | CRLF (RFC 4180) |

All three FlightMemory account display settings that affect the export are handled:

| Setting | Supported formats |
|---|---|
| Date | `MM-DD-YYYY`, `DD.MM.YYYY`, year-only `YYYY` (common for older flights) |
| Distance | Miles and km — km values are converted to miles on output |
| Time | 12-hour (`06:15 pm`) and 24-hour (`18:15`) — departure time is appended to the `Date` field when recorded |

## Field mapping

| OpenFlights field | FlightMemory source | Notes |
|---|---|---|
| `Date` | Date / departure column | Normalised to `YYYY-MM-DD [HH:MM]`; departure time appended when recorded |
| `From` | Departure IATA code | |
| `To` | Arrival IATA code | |
| `Flight_Number` | Airline column, second line | |
| `Airline` | Airline column, first line | |
| `Distance` | Distance column | Always output in miles |
| `Duration` | Duration column | Normalised to `HH:MM` |
| `Seat` | Seat column, text before `/` | |
| `Seat_Type` | Seat column, text after `/` | `Window`→`W`, `Aisle`→`A`, `Middle`→`M` |
| `Class` | First line of seat details block | `First`→`F`, `Business`→`C`, `EconomyPlus`→`P`, `Economy`→`Y` |
| `Reason` | Last line of seat details block | `Personal`→`L`, `Business`→`B`, `Crew`→`C` |
| `Plane` | Aircraft column, first line | |
| `Registration` | Aircraft column, second line | When recorded |
| `Trip`, `Note`, `*_OID` | — | Left empty; assigned by OpenFlights on import |

## Development

```bash
pip install ".[dev]"
pytest
```

Or with uv:

```bash
uv sync --extra dev
uv run pytest
```

## Authors

- Phong Nguyen
- [Claude Sonnet 4.6](https://www.anthropic.com) (Anthropic)
