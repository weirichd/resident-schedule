"""Standalone script to parse Excel rotation schedules using Claude.

Reads an Excel file, sends the full sheet as CSV to the Anthropic API,
and writes the parsed schedule entries into a SQLite database.
"""

import argparse
import json
import logging
import os
import re

from dotenv import load_dotenv

import anthropic
import pandas as pd
import sqlalchemy
from sqlalchemy.orm import Session

from app.models import Base, Resident, Schedule, Vacation

logger = logging.getLogger(__name__)

VALID_ROTATIONS = """
Zollinger Ellison (ZE)
Acute Care Surgery (ACS)
Hepatobiliary Surgery (HPB)
Melanoma and Sarcoma
Breast and Endocrine
East General Surgery
Outpatient
Jeopardy
Transplant
Mount Carmel East
Vascular University Hospital
Vascular East
Colorectal Surgery
Pediatric Surgery
Surgical ICU (SICU)
Breast
Night Float
Endoscopy
Burn
Outpatient Surgical Oncology
Elective
""".strip()

VALID_PROGRAMS = """
General Surgery
Vascular Surgery
Plastic Surgery
Cardiothoracic Surgery
Urology
Orthopedics
ENT
Neurosurgery
Anesthesia
Oral and Maxillofacial Surgery
Emergency Medicine
Family Medicine
Podiatry
Dental Anesthesia
""".strip()

SYSTEM_PROMPT = """\
You are a scheduling data extractor. You will receive a CSV representation of an \
Excel rotation schedule for surgical residents at OSU Hospital. Parse every resident \
rotation assignment and return structured JSON.

## Valid Rotations

Use the full name from this list for the `rotation` field. The abbreviation in \
parentheses shows what you may see in the spreadsheet cells.

{valid_rotations}

If a cell contains a rotation not in this list, use your best judgment to map it to the \
closest match, or use the cell text as-is for `rotation`.

## Valid Programs

{valid_programs}

Use "General Surgery" as the default program. Residents are identified by their program \
based on context: section headers, name suffixes (e.g., "Vascular - McDonnel" means \
the resident's name is McDonnel and their program is Vascular Surgery), or the nature \
of their rotations. The formatting is inconsistent — you may see "Vascular-McDonnel", \
"McDonnel-Vascular", or just "Vascular" with no name. Parse the name and program from \
whatever format is used.

## Rules

1. Each row in the schedule represents a resident. The name column contains the \
resident's last name (sometimes "Last, First" or "Last" only). Clean up names — remove \
program/specialty prefixes and suffixes. \
If a name is "TBD" or contains "TBD" (e.g., "Categorical - TBD", "Prelim - TBD"), \
skip that row entirely. \
If multiple rows share a generic name like "Prelim" (without TBD), each row is a \
different person — disambiguate by appending a number: "Prelim 1", "Prelim 2", etc. \
Number globally across all PGY levels, not per-PGY. \
Rows labeled with just a specialty name (e.g., "Plastics", "Urology", "CT", "Vascular") \
are real residents whose names aren't known yet. Include them using the specialty as the \
name, numbering if there are duplicates at the same PGY level.

2. The PGY (post-graduate year) level is either in a dedicated column or indicated by \
section headers like "PGY-1", "PGY-2", etc. Valid PGY levels are 1-5. If a row has \
PGY 0 or another invalid value, skip it.

3. Date ranges are in header rows. Each rotation cell corresponds to a date range. \
Output dates as YYYY-MM-DD format. The academic year is {academic_year}-{next_year} \
(July {academic_year} through June {next_year}).

4. Split rotations: If a cell contains two rotations separated by "/" (like "ACS/SICU"), \
this means the resident does the first rotation for the first half of the block and the \
second rotation for the second half. Output these as two separate rotation entries. To \
compute the split date: divide the period evenly in half. The first rotation runs from \
the block start_date to the midpoint, and the second rotation runs from the day after \
the midpoint to the block end_date. Exception: compound rotations like "SONC/HPB", \
"Cardiac/CVICU" are single rotations, not splits.

5. FLOAT with explicit date ranges: When a cell contains "FLOAT [date range]" with an \
explicit date range in brackets, use those dates for the FLOAT portion instead of \
midpoint splitting. For example, "FLOAT [7/1-7/26]/ACS" in block 7/1-8/30 means FLOAT \
runs 7/1-7/26 and ACS runs 7/27-8/30. Similarly, "ACS / FLOAT [11/30-12/27]" means ACS \
runs from block start to 11/29 and FLOAT runs 11/30-12/27. If a FLOAT has multiple \
non-contiguous date ranges (e.g., "FLOAT [2/15-2/28, 3/29-4/4] / ACS"), ask for \
clarification — these are unusual and may represent alternating segments.

6. `location`: Set to "East" if the rotation is at the East campus. Any rotation with \
"East" in its name implies location "East" (e.g., "East - ACS" means Acute Care Surgery \
at East, "East Vascular" or "Vascular East" means Vascular East). Otherwise null.

7. East campus rotations: "East - ACS" means rotation="Acute Care Surgery" with \
location="East". "East - General" or just "East" as a rotation maps to \
"East General Surgery". "East Vascular" or "Vascular East" maps to "Vascular East". \
"Vascular - UH" or "Vascular UH" maps to "Vascular University Hospital" (location is \
NOT East).

8. `is_visiting`: Set to true if the resident is from a visiting institution (Doctors \
Hospital, Mount Carmel, Riverside, Kettering, Parkview, etc.). These are typically in \
separate sections of the spreadsheet. Note: OSU residents rotating AT Mount Carmel East \
are NOT visiting — they are on the "Mount Carmel East" rotation.

9. `visiting_institution`: The name of the visiting institution if `is_visiting` is \
true. Otherwise null.

10. Electives and `is_elective`: Rotations like "Elective - HPB", "Elective - Peds", \
"Elective - MIS", "Elective - Vascular", etc. are elective rotations. Set \
`is_elective` to true. Keep the full name including the sub-type (e.g., \
rotation="Elective - HPB", is_elective=true). Do NOT collapse them to just "Elective". \
An elective rotation may use a name not in the valid rotations list — that is fine. \
If the sub-type is "TBD" (e.g., "Elective - TBD"), skip that rotation cell entirely.

11. Vacation blocks: For PGY-1 and PGY-2 residents, when a cell contains "VACATION" as \
the rotation for an entire block, add a vacation entry covering the full block date \
range. For split cells like "BURN/VACATIO" or "VACATION/BURN" in PGY-2, split evenly: \
one half is the rotation (e.g., Burn), the other half produces a vacation entry. \
"Jeopardy/Vacatio" or "Vacation/Jeopardy" follows the same pattern.

12. Vacation/conference annotations: Some rows below a resident contain vacation or \
conference annotations (e.g., "V 8/11-8/17", "C 9/1-9/5"). Extract these as vacation \
entries for the resident above. Use `vac_type` of "vacation" for V annotations and \
"conference" for C annotations.

13. Rows to SKIP — do not include in output:
- Rows with PGY "4-7" (these are program director annotation rows)
- Administrative rows: "Call pool", "switch day", "Main call pool", "East Call Pool", \
"INTERN COMPLIMENTS", "TOTAL", count/complement rows
- Rows without a resident name (just numbers or labels in the name column)
- Rows that are clearly planning notes (e.g., columns with "CONFIRMED", "TENTATIVE", \
interview scheduling notes)
- Rows where the name contains "TBD" (e.g., "Categorical - TBD", "Prelim - TBD")
- If you encounter group rows like "Doctors x 4" or "Anesthesia x 22" and are unsure \
whether each filled block represents a distinct person, ask for clarification.

14. Home-program rotations: Non-General Surgery residents (e.g., Plastics, Urology, \
Orthopedics, Anesthesia) sometimes have blocks where they are on their own service \
(e.g., a Plastics resident with "PLASTICS" in a cell, or a Urology resident with \
"UROLOGY"). Omit these rotation entries — only include rotations where the resident \
is rotating on a general surgery service. Similarly, rotations like "PROCEDURE", \
"SIMULATION", "CT Anesthesia", "CTICU" that are specific to a resident's home program \
should be omitted.

15. SONC sub-rotations: "SONC - HPB", "SONC-Mel/Sarc", "SONC-Breast" are distinct \
rotation sub-types. Keep them as-is (do not collapse to "Outpatient Surgical Oncology"). \
"Outpatient SONC" maps to "Outpatient Surgical Oncology".

16. Date header typos: If a date range in a header row is obviously wrong (e.g., \
"5/3-3/30" which should clearly be "5/3-5/30"), ask for clarification rather than \
guessing.

## Output Format

Return a JSON object (no markdown fences, no extra text) with three keys:

```
{{
  "residents": [
    {{
      "name": "string",
      "pgy": integer,
      "program": "General Surgery",
      "is_visiting": boolean,
      "visiting_institution": "string" or null
    }}
  ],
  "rotations": [
    {{
      "resident": "string (must match a name in residents)",
      "rotation": "full rotation name from valid list",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "location": "East" or null,
      "is_elective": boolean
    }}
  ],
  "vacations": [
    {{
      "resident": "string (must match a name in residents)",
      "vac_start": "YYYY-MM-DD",
      "vac_end": "YYYY-MM-DD",
      "vac_type": "vacation" or "conference"
    }}
  ]
}}
```

## Asking for Clarification

If any part of the schedule is ambiguous or unclear — for example, a rotation name you \
can't confidently map, a name that looks malformed, a date range that doesn't make \
sense, or a section you're unsure how to categorize — you SHOULD ask for clarification \
before producing the final JSON.

To ask questions, respond with a JSON object with a single key "questions" containing \
a list of strings:

```
{{"questions": ["What rotation does 'XYZ' map to?", "Is 'Smith - Urology' a visiting resident?"]}}
```

The user will answer your questions, and then you should produce the final JSON. \
Ask all your questions at once rather than one at a time.

When you are confident about the data and have no questions, return ONLY the JSON \
object with "residents", "rotations", and "vacations" keys. No commentary, no markdown \
code fences.
"""


def excel_to_csv(file_path: str) -> tuple[str, int]:
    """Read an Excel file and convert sheet 1 to a CSV string.

    Returns:
        Tuple of (CSV string, detected academic year start).
    """
    if file_path.endswith(".xlsb"):
        df = pd.read_excel(file_path, engine="pyxlsb", header=None)
    else:
        df = pd.read_excel(file_path, header=None)

    # Auto-detect academic year from filename or cell contents
    year = _detect_year(df, file_path)

    csv_text = df.to_csv(index=False, header=False)
    return csv_text, year


def _detect_year(df: pd.DataFrame, file_path: str) -> int:
    """Detect the academic year start from the file name or contents."""
    # Try filename first: look for patterns like "2025-2026" or "2025-26"
    match = re.search(r"(20\d{2})[-–](20\d{2}|\d{2})", file_path)
    if match:
        return int(match.group(1))

    # Try cell contents
    for row_idx in range(min(10, len(df))):
        for col_idx in range(min(10, df.shape[1])):
            cell = df.iat[row_idx, col_idx]
            if pd.notna(cell):
                cell_str = str(cell)
                match = re.search(r"(20\d{2})[-–](20\d{2}|\d{2})", cell_str)
                if match:
                    return int(match.group(1))

    logger.warning("Could not detect academic year, defaulting to 2025")
    return 2025


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from a response."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text


def _state_file_path(input_file: str) -> str:
    """Derive a deterministic state file path from the input file name."""
    return input_file + ".parse_state.json"


def _save_state(
    state_path: str,
    messages: list,
    csv_text: str,
    year: int,
    model: str,
) -> None:
    """Save conversation state to a JSON file for later resumption."""
    state = {
        "messages": messages,
        "csv_text": csv_text,
        "year": year,
        "model": model,
    }
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
    logger.info("Saved conversation state to %s", state_path)


def _load_state(state_path: str) -> dict:
    """Load conversation state from a JSON file."""
    with open(state_path) as f:
        return json.load(f)


def call_claude(
    csv_text: str,
    year: int,
    model: str = "claude-sonnet-4-20250514",
    answers_file: str | None = None,
    input_file: str | None = None,
) -> dict:
    """Send the CSV to Claude and parse the JSON response.

    Supports a multi-turn clarification loop: if Claude responds with
    {"questions": [...]}, the user is prompted for answers and the
    conversation continues until Claude returns the final JSON.

    When ``answers_file`` is provided, the function loads a previously
    saved conversation state and resumes by sending the answers file
    content as the user's response to Claude's questions.

    Args:
        csv_text: CSV string of the Excel schedule.
        year: Academic year start (e.g., 2025 for 2025-2026).
        model: Anthropic model to use.
        answers_file: Path to a file containing answers to Claude's
            questions from a previous run. When provided, the saved
            conversation state is loaded and resumed.
        input_file: Path to the original input Excel file, used to
            derive the state file path.

    Returns:
        Dict with "residents", "rotations", and "vacations" keys.
    """
    client = anthropic.Anthropic()

    state_path = _state_file_path(input_file) if input_file else None

    # If resuming from a saved state with answers
    if answers_file:
        if not state_path or not os.path.exists(state_path):
            raise FileNotFoundError(
                f"No saved conversation state found at {state_path}. "
                "Run without --answers first to start a new parse."
            )

        state = _load_state(state_path)
        messages = state["messages"]
        csv_text = state["csv_text"]
        year = state["year"]
        model = state["model"]

        with open(answers_file) as f:
            answers_content = f.read().strip()

        # Append the answers as the user response
        messages.append({"role": "user", "content": answers_content})
        logger.info(
            "Resumed conversation from %s with answers from %s",
            state_path,
            answers_file,
        )
    else:
        messages = [
            {
                "role": "user",
                "content": (
                    "Here is the rotation schedule as CSV. "
                    "Parse it and return JSON.\n\n" + csv_text
                ),
            }
        ]

    system_prompt = SYSTEM_PROMPT.format(
        valid_rotations=VALID_ROTATIONS,
        valid_programs=VALID_PROGRAMS,
        academic_year=year,
        next_year=year + 1,
    )

    while True:
        logger.info("Calling Claude (%s)...", model)

        message = client.messages.create(
            model=model,
            max_tokens=16000,
            system=system_prompt,
            messages=messages,
        )

        response_text = message.content[0].text
        logger.debug("Raw response length: %d chars", len(response_text))

        parsed = json.loads(_strip_fences(response_text))

        # Check if Claude is asking questions
        if isinstance(parsed, dict) and "questions" in parsed:
            questions = parsed["questions"]
            print("\nClaude has questions about the schedule:\n")
            for i, q in enumerate(questions, 1):
                print(f"  {i}. {q}")
            print()

            # Add the assistant's question message to the conversation
            messages.append({"role": "assistant", "content": response_text})

            # Save state so the user can resume later with --answers
            if state_path:
                _save_state(state_path, messages, csv_text, year, model)
                print(
                    f"Conversation state saved to {state_path}\n"
                    f"To resume later, write your answers to a file and run:\n"
                    f"  python parse_schedule.py --file {input_file} "
                    f"--output <db> --answers <answers_file>\n"
                )

            answers = input("Your answers (or 'skip' to proceed without answering): ")

            if answers.strip().lower() == "skip":
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "I don't have answers to these questions. "
                            "Use your best judgment and produce the final JSON array."
                        ),
                    }
                )
            else:
                messages.append({"role": "user", "content": answers})
            continue

        # Should be the final JSON object with residents/rotations/vacations
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
        for key in ("residents", "rotations", "vacations"):
            if key not in parsed:
                raise ValueError(f"Missing required key: {key}")

        # Clean up state file on successful completion
        if state_path and os.path.exists(state_path):
            os.remove(state_path)
            logger.info("Removed state file %s", state_path)

        return parsed


def write_to_db(data: dict, db_path: str) -> None:
    """Write parsed data to the SQLite database.

    Args:
        data: Dict with "residents", "rotations", and "vacations" keys.
        db_path: Path to the output SQLite database file.
    """
    engine = sqlalchemy.create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = Session(engine)
    try:
        # Insert residents and build name -> id map
        resident_ids: dict[str, int] = {}
        for r in data["residents"]:
            resident = Resident(
                name=r["name"],
                pgy=r["pgy"],
                program=r.get("program", "General Surgery"),
                is_visiting=1 if r.get("is_visiting") else 0,
                visiting_institution=r.get("visiting_institution"),
            )
            session.add(resident)
            session.flush()
            resident_ids[r["name"]] = resident.id

        # Insert rotations
        for rot in data["rotations"]:
            resident_id = resident_ids.get(rot["resident"])
            if resident_id is None:
                logger.warning(
                    "Rotation references unknown resident: %s", rot["resident"]
                )
                continue
            entry = Schedule(
                resident_id=resident_id,
                start_date=rot["start_date"],
                end_date=rot["end_date"],
                rotation=rot["rotation"],
                location=rot.get("location"),
                is_elective=1 if rot.get("is_elective") else 0,
            )
            session.add(entry)

        # Insert vacations
        for vac in data["vacations"]:
            resident_id = resident_ids.get(vac["resident"])
            if resident_id is None:
                logger.warning(
                    "Vacation references unknown resident: %s", vac["resident"]
                )
                continue
            vac_row = Vacation(
                resident_id=resident_id,
                vac_start=vac["vac_start"],
                vac_end=vac["vac_end"],
                vac_type=vac.get("vac_type", "vacation"),
            )
            session.add(vac_row)

        session.commit()
        logger.info(
            "Wrote %d residents, %d rotations, %d vacations to %s",
            len(data["residents"]),
            len(data["rotations"]),
            len(data["vacations"]),
            db_path,
        )

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Parse Excel rotation schedule using Claude API."
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        required=True,
        help="Input Excel file (.xlsx or .xlsb)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Output SQLite database file",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Academic year start (e.g., 2025). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-20250514",
        help="Anthropic model to use (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and display results without writing to database",
    )
    parser.add_argument(
        "--answers",
        type=str,
        help=(
            "Path to a file containing answers to Claude's questions "
            "from a previous interrupted run. Resumes the saved conversation."
        ),
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Step 1: Load Excel
    logger.info("Reading %s...", args.file)
    csv_text, year = excel_to_csv(args.file)
    if args.year:
        year = args.year
    logger.info("Academic year: %d-%d", year, year + 1)
    logger.info("CSV size: %d chars", len(csv_text))

    # Step 2: Call Claude
    data = call_claude(
        csv_text,
        year,
        model=args.model,
        answers_file=args.answers,
        input_file=args.file,
    )

    residents = data["residents"]
    rotations = data["rotations"]
    vacations = data["vacations"]

    # Summary
    visiting = [r for r in residents if r.get("is_visiting")]
    programs = {r.get("program", "General Surgery") for r in residents}

    logger.info("  Residents: %d", len(residents))
    logger.info("  Rotations: %d", len(rotations))
    logger.info("  Vacations: %d", len(vacations))
    logger.info("  Visiting: %d", len(visiting))
    logger.info("  Programs: %s", ", ".join(sorted(programs)))

    if args.debug:
        for r in residents:
            visit_str = (
                f" [visiting from {r['visiting_institution']}]"
                if r.get("is_visiting")
                else ""
            )
            print(f"  PGY{r['pgy']} {r['name']} ({r.get('program', '?')}){visit_str}")

        print()
        for rot in rotations:
            loc_str = f" ({rot['location']})" if rot.get("location") else ""
            elec_str = " [elective]" if rot.get("is_elective") else ""
            print(
                f"  {rot['resident']}: {rot['rotation']}{loc_str}{elec_str} "
                f"({rot['start_date']} to {rot['end_date']})"
            )

        if vacations:
            print()
            for v in vacations:
                print(
                    f"  {v['resident']}: {v['vac_type']} "
                    f"{v['vac_start']} to {v['vac_end']}"
                )

    if args.dry_run:
        logger.info("Dry run — not writing to database")
        return

    # Step 3: Write to DB
    write_to_db(data, args.output)
    logger.info("Done!")


if __name__ == "__main__":
    main()
