# FlightMemory HTML export format

Technical reference for the FlightMemory FlightData HTML export as
observed on the site as of 2026-06-21. Intended for maintainers of the
parser in `src/flightmemory_to_openflight_csv/convert.py`.

---

## File characteristics

- Encoding: UTF-8 (declared via `<meta charset="UTF-8">`)
- DOCTYPE: HTML5
- The file is a snapshot of a live page, so it contains navigation,
  styling links, and form elements that are irrelevant to parsing.
- FlightMemory paginates at 50 flights per page. Multiple files must be
  combined to cover a full history.

---

## Locating the flight table

There is one main data table per file. It carries no `id` attribute, but
can be identified by finding any `<td class="liste_gross">` element and
walking up to its nearest `<table>` ancestor:

```
table[width="100%"][border="0"][cellspacing="2"][cellpadding="2"]
```

The same table also contains a header/sorting row and pagination rows
which are skipped automatically because they do not match the 10-cell
flight-row signature (see below).

---

## Row structure

Each flight record is represented by **three consecutive `<tr>` rows** in
the main table:

| Row | Cells | Content |
|-----|-------|---------|
| Main row | 10 | All flight metadata |
| Distance row | 2 | Numeric value + unit string |
| Duration row | 2 | Numeric value + unit string |

The parser identifies a main row by:
- exactly 10 `<td>` direct children, **and**
- `cells[0]` has `class="liste_gross"`

The following two rows are then consumed as the distance and duration
rows. Any other row (header, pagination, nested-table artefact) is
skipped with `i += 1`.

---

## Main row: cell-by-cell reference

### Cell[0] — Row number and optional overall impression

```html
<!-- No overall rating set -->
<td align="right" class="liste_gross">241<br/></td>

<!-- Overall impression rating present -->
<td align="right" class="liste_gross">239<br/>
  <img height="18" src="/images/star_2.gif" title="Overall impression: bad" width="18"/>
</td>
```

The FlightMemory internal sequence number (highest = most recent).
When an overall impression rating has been entered, a star `<img>` appears
after the sequence number. Extracted via `_star_rating(cells[0])` and
recorded in the `Note` output field as `overall=N`.

---

### Cell[1] — Date and optional departure/arrival times

```html
<!-- Date only -->
<td class="liste"><nobr>12-31-2024</nobr><br/><br/> </td>

<!-- Date with departure and arrival times (12-hour) -->
<td class="liste"><nobr>12-31-2024</nobr><br/>09:00 pm<br/>06:00 am +1</td>

<!-- Date with departure and arrival times (24-hour) -->
<td class="liste"><nobr>31.12.2024</nobr><br/>21:00<br/>06:00 +1</td>
```

**Date** is always inside the `<nobr>` tag. Three formats are used
depending on the account's date display setting:

| Format | Example | Notes |
|--------|---------|-------|
| `MM-DD-YYYY` | `12-31-2024` | US locale setting |
| `DD.MM.YYYY` | `31.12.2024` | European locale setting |
| `YYYY` | `2008` | Year-only; used for older flights where the exact date was not recorded |

**Departure and arrival times** appear as bare text nodes separated by
`<br/>` tags after the `<nobr>` block. They are absent for most flights.
When present they follow one of two formats depending on the account's
time display setting:

| Format | Example |
|--------|---------|
| 12-hour | `09:00 pm` |
| 24-hour | `21:00` |

The **arrival time** may carry a `+1` suffix (e.g. `06:00 am +1`) to
indicate the flight lands the following calendar day. This suffix is part
of the arrival time text node and does not affect the date or departure
time. The arrival time is not used in the OpenFlights output (OpenFlights
derives arrival from `Date + Duration`).

**Extraction:** `nobr.get_text()` for the date; then iterate
`cell.children`, skip `<nobr>` and `<br>` nodes, and collect remaining
stripped text nodes — `[0]` is departure time, `[1]` is arrival time.

---

### Cell[2] — Departure airport

```html
<td class="liste_gross">
  <b>LAX</b><br/>
  <!-- optional star rating (see Star Ratings section) -->
</td>
```

The IATA code is in the `<b>` tag. An optional `<img>` star-rating
element may follow.

---

### Cell[3] — Departure airport details

```html
<td class="liste">
  <b>Los Angeles</b><br/>
  USA<br/>
  International
</td>
```

City (`<b>`), country, and airport name separated by `<br/>`. Not used
in the OpenFlights output (OpenFlights resolves details from the IATA
code).

---

### Cell[4] — Arrival airport

Identical structure to Cell[2].

---

### Cell[5] — Arrival airport details

Identical structure to Cell[3].

---

### Cell[6] — Airline and flight number

```html
<!-- With flight number -->
<td class="liste">
  Delta Air Lines<br/>
  3969<br/>
  <!-- optional star rating -->
</td>

<!-- Without flight number -->
<td class="liste">
  Southwest Airlines
  <!-- optional star rating -->
</td>
```

Line 0: airline name. Line 1: flight number (digits only, no prefix
letter). Either or both may be absent. The optional star-rating `<img>`
has no text content and does not affect `get_text()` output.

---

### Cell[7] — Aircraft

```html
<!-- Type only -->
<td class="liste">Embraer 175</td>

<!-- Type + registration -->
<td class="liste">Boeing 757-200<br/>N727TW</td>

<!-- Type + registration + plane name -->
<td class="liste">
  Airbus 321<br/>
  N985JT<br/>
  Some Plane Name<br/>
  <!-- optional star rating -->
</td>
```

Text lines in order:
- Line 0: aircraft type (always present when cell is non-empty)
- Line 1: registration/tail number (optional; typically N-number format
  for US-registered aircraft)
- Line 2: individual aircraft name/nickname (optional; user-entered)

The optional star-rating `<img>` appears after all text lines and
produces no text.

---

### Cell[8] — Seat, class, and reason

```html
<!-- Seat number + type, with class recorded -->
<td class="liste">
  17A/Window<br/>
  <small>Business<br/>Passenger<br/>Personal</small>
</td>

<!-- No seat number, aisle type, no class recorded -->
<td class="liste">
  /Aisle<br/>
  <small><br/>Passenger<br/>Personal</small>
</td>

<!-- No seat info at all -->
<td class="liste">
  / <br/>
  <small>EconomyPlus<br/>Passenger<br/>Personal</small>
</td>
```

**Seat info** (the text before the first `<br/>`) has the form
`{seat_number}/{seat_type}`, where either part can be empty. `seat_type`
is one of: `Window`, `Aisle`, `Middle`, `unspecified` (or blank).

**`<small>` block** contains 2 or 3 `<br/>`-separated lines:

| Lines present | Line 0 | Line 1 | Line 2 |
|---------------|--------|--------|--------|
| 3 | Seat class | `Passenger` | Trip reason |
| 2 | `Passenger` | Trip reason | — |

The 2-line variant occurs when no seat class was recorded. The class line
is replaced by a leading `<br/>` inside `<small>`, which becomes an empty
string after splitting and is filtered out, leaving only 2 non-empty
lines.

**Important:** reason must be read from the **last** line of the filtered
list (`lines[-1]`), not from the absolute index `lines[2]`, to handle
both the 2-line and 3-line variants correctly.

Known seat class values and their OpenFlights mappings:

| FlightMemory | OpenFlights |
|---|---|
| `First` | `F` |
| `Business` | `C` |
| `EconomyPlus` | `P` |
| `Economy` | `Y` |

The middle line of `<small>` is the passenger role. Known values:
`Passenger`, `Crew`, `Cockpit`. This line is skipped during parsing
(it is not mapped to any OpenFlights field).

Known trip reason values (last line of `<small>`):

| FlightMemory | OpenFlights |
|---|---|
| `Personal` | `L` |
| `Business` | `B` |
| `Crew` | `C` |
| `Virtuell` | `O` (Other; simulator/virtual flight) |

---

### Cell[9] — Options (and user note)

```html
<!-- No note -->
<td class="liste"><br/><select ...>...</select></td>

<!-- With note -->
<td class="liste">
  <span title="Note text goes here.">Note</span><br/>
  <select ...>...</select>
</td>
```

This cell is primarily a navigation widget and is otherwise ignored. The
exception is a user-entered flight note: when present it appears as a
`<span title="...">Note</span>` element, with the note text in the
`title` attribute (not the element's text content).

---

## Distance row

```html
<tr>
  <td align="right">308 </td>
  <td>mi</td>
</tr>

<tr>
  <td align="right">4,157 </td>
  <td>km</td>
</tr>
```

`cells[0]`: numeric distance value, possibly with a thousands comma
(e.g. `4,157`). `cells[1]`: unit string, either `mi` or `km` depending
on the account's distance display setting. The converter normalises to
miles (`km / 1.60934`, rounded to the nearest integer).

---

## Duration row

```html
<tr>
  <td align="right">5:07 </td>
  <td>h</td>
</tr>
```

`cells[0]`: duration in `H:MM` or `HH:MM` format. `cells[1]`: always
`h`. The converter zero-pads the hour to produce `HH:MM`.

---

## Star ratings

Optional star ratings appear as `<img>` elements in cells[2], [4], [6],
and [7]. The star count (1–5) is encoded in the image filename:

```html
<img src="/images/star_1.gif" title="Rating: real bad" width="18" height="18"/>
<img src="/images/star_5.gif" title="Rating: excellent" width="18" height="18"/>
```

Pattern: `/images/star_(\d)\.gif`. The `title` attribute contains a
human-readable label but the parser only uses the captured digit.

Because OpenFlights has no dedicated rating fields, ratings are packed
into the `Note` output field alongside the user note and plane name:

```
Example note. [plane: Some Plane Name] [ratings: dep_airport=5, arr_airport=3, airline=2, airplane=1]
```

---

## Fields present in FlightMemory but absent from the table export

The following fields exist in the FlightMemory data model (visible on the
edit and detail pages) but do **not** appear in the FlightData table HTML
and therefore cannot be extracted by this parser:

| Field | Edit-page name | Notes |
|---|---|---|
| Rating sub-reasons | `bewertung_grund`, `bewert_grund_*` | One per entity (overall, dep airport, arr airport, airline, aircraft); stored but not rendered in the table |
| Arrival date | `an_datum_eingabe` | The table only shows `+1` on the arrival time when the date differs from departure; the actual arrival date is not in the table HTML |

The **overall impression** rating (`bewertung`) is present in the table
HTML when set (cell[0] `<img>`) and is captured.

The **arrival time** (`an_zeit_eingabe`) appears in cell[1] as the second
text node after the departure time, but OpenFlights has no arrival-time
field (arrival is implied by `Date + Duration`) so it is not used.

---

## Known edge cases

| Situation | Behaviour |
|---|---|
| Year-only date (`YYYY`) | Passed through as-is; OpenFlights accepts `YYYY` |
| Arrival time with `+1` suffix | `+1` is part of the arrival time text node; ignored (parser only reads departure time) |
| `<small>` with 2 lines (no class) | Reason read from `lines[-1]`; class left empty |
| Distance in km | Converted to miles via `round(km / 1.60934)` |
| 12-hour time | Normalised to 24-hour `HH:MM` via `strptime("%I:%M %p")` |
| Seat type `unspecified` | Falls through `SEAT_TYPE_MAP`; written as empty string |
| Flights with no times | `time_texts` list is empty; date written without time suffix |
| Nested tables in header row | `find_all("tr")` is recursive; extra rows appear in the list but do not match the 10-cell signature and are skipped |
