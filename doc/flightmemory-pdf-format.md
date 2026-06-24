# FlightMemory PDF export format

Technical reference for the FlightMemory PDF export as observed on the
site as of 2026-06-21. Intended for maintainers of the parser in
`src/flightmemory_to_openflight_csv/pdf.py` (shared helpers live in
`_core.py`).

---

## File characteristics

- Format: PDF/A-style, produced by the FlightMemory web server
- Page size: A4 (595 × 842 pt)
- Pages: one per ~17 flights (varies by row height)
- Required library: `pdfplumber` (`pip install 'flightmemory-to-openflight-csv[pdf]'`)
- Extraction method: `page.extract_words(x_tolerance=1)` — a tight x-tolerance
  is required to prevent the `No.` and `Date` values from being concatenated into
  a single word token by pdfplumber's default gap-filling heuristic

---

## Page layout

Each page has three zones:

| Zone | y range | Content |
|---|---|---|
| Header | 0 – 120 pt | FlightMemory banner + column header row |
| Data | 120 – 800 pt | Flight rows |
| Footer | 800 – 842 pt | Date, URL, page number |

Only the data zone is parsed.

---

## Column layout

Columns are assigned by the x0 coordinate of each word. Boundaries are
calibrated against observed data positions (data words sit 0–1 pt to the
left of their column header labels):

| Column key | x0 range | Content |
|---|---|---|
| `no` | [0, 31) | Flight sequence number |
| `date` | [31, 79) | Date + departure time + arrival time |
| `dep_iata` | [79, 102) | Departure IATA code |
| `dep_det` | [102, 164) | Departure city / country / airport name |
| `arr_iata` | [164, 187) | Arrival IATA code |
| `arr_det` | [187, 249) | Arrival city / country / airport name |
| `distance` | [249, 288) | Distance (line 1) and duration (line 2) |
| `airline` | [288, 359) | Airline name (line 1) and flight number (line 2) |
| `airplane` | [359, 442) | Aircraft type / registration / plane name / reason |
| `seat` | [442, 487) | Seat number / seat type / class / pax role |
| `comment` | [487, ∞) | Free-text user note |

---

## Row detection

A new flight row begins at the y-coordinate (`top`) of any word that:
- falls in the `no` column (x0 < 31), **and**
- consists entirely of digits

The block of words belonging to that row extends from its `top` value up
to (but not including) the `top` of the next row.

---

## Multi-line cell content

Within each column, words are grouped into text lines using a vertical
tolerance of 3 pt. Lines are then joined with spaces and returned in
top-to-bottom order.

---

## Column-by-column field reference

### `no` — Sequence number

Single word; ignored in output (used only for row detection).

---

### `date` — Date and times

```
Line 0:  12-14-2023          ← departure date
Line 1:  10:24 pm            ← departure time (optional; 12- or 24-hour)
Line 2:  06:48 am +1         ← arrival time (optional; may carry +1 suffix)
```

Date formats match the HTML export: `MM-DD-YYYY`, `DD.MM.YYYY`, or
bare `YYYY`. Time formats match the account's time display setting.

Arrival time (`line 2`) is not used — OpenFlights derives arrival from
`Date + Duration`. The `+1` suffix on arrival time is safely ignored.

---

### `dep_iata` / `arr_iata` — IATA codes

Single word per column; always on the first line.

---

### `dep_det` / `arr_det` — Airport details

```
Line 0:  San Francisco       ← city (may be multi-word)
Line 1:  USA                 ← country
Line 2:  International       ← airport name (may be multi-word)
```

Not used in the OpenFlights output (OpenFlights resolves details from
the IATA code).

---

### `distance` — Distance and duration

```
Line 0:  2,583 mi            ← distance value + unit ("mi" or "km")
Line 1:  5:24 h              ← duration value + "h"
```

Both distance and duration share the same column. Distance is on the
first line; duration is on the second. km values are converted to miles
(`round(km / 1.60934)`). Duration is normalised to `HH:MM`.

---

### `airline` — Airline and flight number

```
Line 0:  JetBlue             ← airline name (may be multi-word)
Line 1:  2416                ← flight number (optional)
```

---

### `airplane` — Aircraft, registration, plane name, and reason

```
Line 0:  Airbus 321          ← aircraft type
Line 1:  N985JT              ← registration (optional)
Line 2:  City of Nowhere     ← individual aircraft name (optional)
Line 3:  Personal            ← flight reason (Personal/Business/Crew/Virtuell)
```

The reason is detected by matching the **last line** against `REASON_MAP`.
After removing it, remaining lines (in order) are registration and plane
name. This handles all variants:

| Lines present | Interpretation |
|---|---|
| `[type]` | type only; no reason |
| `[type, reason]` | type + reason; no registration |
| `[type, reg, reason]` | type + registration + reason |
| `[type, reg, name, reason]` | all four fields |

---

### `seat` — Seat number, type, class, and passenger role

```
Line 0:  3A                  ← seat number (optional)
Line 1:  Window              ← seat type (optional)
Line 2:  Business            ← travel class (optional)
Line 3:  Passenger           ← passenger role (Passenger/Crew/Cockpit)
```

Lines are assigned by value rather than position: known seat-type
keywords (`Window`, `Aisle`, `Middle`) map to `Seat_Type`; known class
keywords (`Economy`, `EconomyPlus`, `Business`, `First`) map to `Class`;
known pax-role keywords (`Passenger`, `Crew`, `Cockpit`) are discarded;
anything else is the seat number.

---

### `comment` — User note

Free-text note across one or more lines; joined with spaces.

---

## Comparison with the HTML export

| Field | HTML table | PDF |
|---|---|---|
| Star ratings (overall, per entity) | ✓ | ✗ (no images in PDF) |
| User note | Via `<span title="...">` | Directly as text |
| Departure time | Via text nodes in date cell | `date` column line 1 |
| Arrival time | Via text nodes in date cell | `date` column line 2 |
| Plane name | Cell[7] line 2 | `airplane` column line 2 or 3 |
| Flight reason | `<small>` last line | `airplane` column last line |
| Seat details | `<small>` block | `seat` column lines |

Star ratings are not recoverable from the PDF. All other fields are
present in both formats.
