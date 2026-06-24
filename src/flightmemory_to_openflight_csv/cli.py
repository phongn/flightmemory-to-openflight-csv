"""Command-line entry point for the FlightMemory converter."""

import argparse
import sys
from pathlib import Path

from ._core import Flight, write_openflights_csv
from .html import parse_html_file
from .pdf import parse_pdf_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert FlightMemory exports (HTML or PDF) to OpenFlights CSV."
    )
    parser.add_argument("files", nargs="+", type=Path, metavar="FILE")
    parser.add_argument("-o", "--output", type=Path, default=Path("flights.csv"))
    args = parser.parse_args()

    all_flights: list[Flight] = []
    for path in args.files:
        if path.suffix.lower() == ".pdf":
            flights = parse_pdf_file(path)
        else:
            flights = parse_html_file(path)
        all_flights.extend(flights)

    all_flights.sort(key=lambda f: f["Date"], reverse=True)
    write_openflights_csv(all_flights, args.output)
    print(f"Wrote {len(all_flights)} flights to {args.output}", file=sys.stderr)
