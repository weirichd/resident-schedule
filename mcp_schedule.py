"""MCP server for resident schedule parsing.

Exposes tools to read Excel schedule files as CSV and write parsed
schedule data to the SQLite database, so Claude Code can do the
parsing itself without separate API calls.
"""

import json
import logging

import pandas as pd
import sqlalchemy
from sqlalchemy.orm import Session

from mcp.server.fastmcp import FastMCP

from app.models import Base, Resident, Schedule, Vacation

logger = logging.getLogger(__name__)

mcp = FastMCP("resident-schedule")


@mcp.tool()
def read_schedule_csv(file_path: str) -> str:
    """Read an Excel schedule file and return its contents as CSV.

    Args:
        file_path: Path to the Excel file (.xlsx or .xlsb).

    Returns:
        CSV string of the first sheet, suitable for parsing.
    """
    if file_path.endswith(".xlsb"):
        df = pd.read_excel(file_path, engine="pyxlsb", header=None)
    else:
        df = pd.read_excel(file_path, header=None)

    return df.to_csv(index=False, header=False)


@mcp.tool()
def read_schedule_sheet(file_path: str, sheet_name: str) -> str:
    """Read a specific sheet from an Excel schedule file as CSV.

    Args:
        file_path: Path to the Excel file (.xlsx or .xlsb).
        sheet_name: Name of the sheet to read.

    Returns:
        CSV string of the specified sheet.
    """
    if file_path.endswith(".xlsb"):
        df = pd.read_excel(
            file_path, sheet_name=sheet_name, engine="pyxlsb", header=None
        )
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    return df.to_csv(index=False, header=False)


@mcp.tool()
def list_sheets(file_path: str) -> str:
    """List all sheet names in an Excel file.

    Args:
        file_path: Path to the Excel file (.xlsx or .xlsb).

    Returns:
        JSON array of sheet names.
    """
    xls = pd.ExcelFile(file_path)
    return json.dumps(xls.sheet_names)


@mcp.tool()
def write_schedule_db(data_json: str, db_path: str) -> str:
    """Write parsed schedule data to the SQLite database.

    Drops and recreates all tables, then inserts the provided data.

    Args:
        data_json: JSON string with three keys:
            - residents: list of resident objects with fields:
                index, name, pgy, program, is_visiting,
                visiting_institution, is_prelim, is_name
            - rotations: list of rotation objects with fields:
                resident_index, rotation, start_date, end_date,
                location, is_elective
            - vacations: list of vacation objects with fields:
                resident_index, vac_start, vac_end, vac_type
        db_path: Path to the output SQLite database file.

    Returns:
        Summary of what was written.
    """
    data = json.loads(data_json)

    engine = sqlalchemy.create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = Session(engine)
    try:
        resident_ids: dict[int, int] = {}
        for r in data["residents"]:
            resident = Resident(
                name=r["name"],
                pgy=r["pgy"],
                program=r.get("program", "General Surgery"),
                is_visiting=1 if r.get("is_visiting") else 0,
                visiting_institution=r.get("visiting_institution"),
                is_prelim=1 if r.get("is_prelim") else 0,
                is_name=1 if r.get("is_name", True) else 0,
            )
            session.add(resident)
            session.flush()
            resident_ids[r["index"]] = resident.id

        for rot in data["rotations"]:
            resident_id = resident_ids.get(rot["resident_index"])
            if resident_id is None:
                logger.warning(
                    "Rotation references unknown resident index: %s",
                    rot["resident_index"],
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

        for vac in data["vacations"]:
            resident_id = resident_ids.get(vac["resident_index"])
            if resident_id is None:
                logger.warning(
                    "Vacation references unknown resident index: %s",
                    vac["resident_index"],
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

        summary = (
            f"Wrote {len(data['residents'])} residents, "
            f"{len(data['rotations'])} rotations, "
            f"{len(data['vacations'])} vacations to {db_path}"
        )
        return summary

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
