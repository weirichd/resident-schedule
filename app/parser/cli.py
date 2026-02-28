"""CLI entry point for the automated Excel parser."""

import argparse
import logging
import sys

import sqlalchemy
from sqlalchemy.orm import Session

from app.models import Base, RotationMap, Schedule, Vacation
from app.parser.excel_parser import (
    get_rotation_map_entries,
    parse_excel,
    resolve_vacation_dates,
)
from app.parser.llm_excel_parser import parse_excel_llm


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Parse Excel rotation schedule into SQLite database."
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        required=True,
        help="Input Excel file (.xlsx or .xlsb)",
    )
    parser.add_argument(
        "--output", "-o", type=str, required=True, help="Output SQLite database file"
    )
    parser.add_argument("--year", type=int, help="Academic year start (e.g., 2025)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and display results without writing to database",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM-powered parser instead of rules-based",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help=(
            "Override the LLM model name "
            "(default: claude-haiku-4-5 for Anthropic, llama3.2 for ollama)"
        ),
    )

    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    logger = logging.getLogger(__name__)

    # Parse the Excel file
    if args.llm:
        logger.info(f"Parsing {args.file} with LLM parser...")
        rows, academic_year = parse_excel_llm(
            args.file,
            year=args.year,
            debug=args.debug,
            model=args.llm_model,
            ollama_model=args.llm_model,
        )
    else:
        logger.info(f"Parsing {args.file}...")
        rows, academic_year = parse_excel(args.file, year=args.year, debug=args.debug)

    # Resolve vacation M/D dates to full YYYY-MM-DD
    resolve_vacation_dates(rows, academic_year)

    if not rows:
        logger.error("No data parsed from the file!")
        sys.exit(1)

    logger.info(f"Parsed {len(rows)} schedule entries")

    # Summary
    names = set(r.name for r in rows)
    rotations = set(r.rotation for r in rows)
    visiting = [r for r in rows if r.is_visiting]
    vac_count = sum(len(r.vacations) for r in rows)

    logger.info(f"  Residents: {len(names)}")
    logger.info(f"  Rotations: {len(rotations)}")
    logger.info(f"  Visiting entries: {len(visiting)}")
    logger.info(f"  Vacation/conference annotations: {vac_count}")

    if args.debug:
        for r in rows:
            vac_str = ""
            if r.vacations:
                vac_str = (
                    " ["
                    + ", ".join(
                        f"{v.vac_type}: {v.vac_start}-{v.vac_end}" for v in r.vacations
                    )
                    + "]"
                )
            loc_str = f" ({r.location})" if r.location else ""
            visit_str = (
                f" [visiting from {r.visiting_institution}]" if r.is_visiting else ""
            )
            print(
                f"  PGY{r.pgy} {r.name}: {r.rotation_full}{loc_str} "
                f"({r.start_date} to {r.end_date}){vac_str}{visit_str}"
            )

    if args.dry_run:
        logger.info("Dry run — not writing to database")
        return

    # Write to database
    logger.info(f"Writing to {args.output}...")
    engine = sqlalchemy.create_engine(f"sqlite:///{args.output}", echo=False)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = Session(engine)
    try:
        # Insert schedule rows
        schedule_map: dict[tuple[str, str, str], int] = {}
        for r in rows:
            entry = Schedule(
                start_date=r.start_date,
                end_date=r.end_date,
                name=r.name,
                pgy=r.pgy,
                rotation=r.rotation,
                rotation_full=r.rotation_full,
                location=r.location,
                is_visiting=1 if r.is_visiting else 0,
                visiting_institution=r.visiting_institution,
            )
            session.add(entry)
            session.flush()  # Get the ID
            schedule_map[(r.name, r.rotation, r.start_date)] = entry.id

            # Insert vacations
            for v in r.vacations:
                vac = Vacation(
                    schedule_id=entry.id,
                    vac_start=v.vac_start,
                    vac_end=v.vac_end,
                    vac_type=v.vac_type,
                    approved_status=v.approved_status,
                    covered_by=v.covered_by,
                )
                session.add(vac)

        # Insert rotation map
        for entry in get_rotation_map_entries(rows):
            rm = RotationMap(
                abbrev=entry["abbrev"],
                full_name=entry["full_name"],
                is_common=entry["is_common"],
            )
            session.add(rm)

        session.commit()
        logger.info("Database written successfully!")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
