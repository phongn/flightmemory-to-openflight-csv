"""Command-line entry point for the FlightMemory converter."""

import argparse
import sys
from pathlib import Path

from ._core import Flight, FlightMemoryError, ParseResult, write_openflights_csv
from .html import parse_html_file
from .pdf import parse_pdf_file


def _parse_one(path: Path) -> ParseResult:
    if path.suffix.lower() == ".pdf":
        return parse_pdf_file(path)
    return parse_html_file(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert FlightMemory exports (HTML or PDF) to OpenFlights CSV."
    )
    parser.add_argument("files", nargs="+", type=Path, metavar="FILE")
    parser.add_argument("-o", "--output", type=Path, default=Path("flights.csv"))
    args = parser.parse_args()

    all_flights: list[Flight] = []
    total_issues = 0
    failed_files = 0

    for path in args.files:
        try:
            result = _parse_one(path)
        except FlightMemoryError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            failed_files += 1
            continue
        except Exception as e:  # unreadable/corrupt file — report and keep going
            print(f"ERROR: {path.name}: {e}", file=sys.stderr)
            failed_files += 1
            continue

        summary = f"{path.name}: {len(result.flights)} flights"
        if result.issues:
            summary += f", {len(result.issues)} issue(s)"
        print(summary, file=sys.stderr)
        for issue in result.issues:
            print(f"  - {issue.location}: {issue.message}", file=sys.stderr)

        total_issues += len(result.issues)
        all_flights.extend(result.flights)

    if not all_flights:
        print("No flights parsed; output not written.", file=sys.stderr)
        return 1

    all_flights.sort(key=lambda f: f["Date"], reverse=True)
    write_openflights_csv(all_flights, args.output)

    print(
        f"Wrote {len(all_flights)} flights to {args.output} "
        f"({total_issues} issue(s), {failed_files} file(s) failed).",
        file=sys.stderr,
    )
    return 1 if failed_files else 0


if __name__ == "__main__":
    sys.exit(main())
