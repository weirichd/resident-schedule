from typing import Optional

import pandas as pd
from sqlalchemy import func, case
from sqlalchemy.orm import Session, joinedload

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models import Schedule, Vacation, RotationMap

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")


def get_session() -> Session:
    return SessionLocal()


def get_data_from_date(
    date: Optional[str] = None, include_visiting: bool = True
) -> pd.DataFrame:
    session = get_session()
    try:
        q = session.query(Schedule).options(joinedload(Schedule.vacations))

        if date is None:
            date = pd.Timestamp.now().strftime("%Y-%m-%d")

        q = q.filter(
            func.date(date) >= func.date(Schedule.start_date),
            func.date(date) <= func.date(Schedule.end_date),
        )

        if not include_visiting:
            q = q.filter(Schedule.is_visiting == 0)

        entries = q.all()
        return _entries_to_dataframe(entries)
    finally:
        session.close()


def get_rotation_schedule(rotation: str, include_visiting: bool = True) -> pd.DataFrame:
    session = get_session()
    try:
        q = (
            session.query(Schedule)
            .options(joinedload(Schedule.vacations))
            .filter(Schedule.rotation == rotation)
            .order_by(Schedule.start_date)
        )

        if not include_visiting:
            q = q.filter(Schedule.is_visiting == 0)

        entries = q.all()
        return _entries_to_dataframe(entries)
    finally:
        session.close()


def get_resident_schedule(name: str) -> pd.DataFrame:
    session = get_session()
    try:
        entries = (
            session.query(Schedule)
            .options(joinedload(Schedule.vacations))
            .filter(Schedule.name == name)
            .order_by(Schedule.start_date)
            .all()
        )
        return _entries_to_dataframe(entries)
    finally:
        session.close()


def get_all_rotation_names() -> list[dict]:
    """Get all rotation names, sorted: common first (alphabetical), then uncommon."""
    session = get_session()
    try:
        rotations = (
            session.query(
                Schedule.rotation,
                Schedule.rotation_full,
            )
            .group_by(Schedule.rotation, Schedule.rotation_full)
            .all()
        )

        # Join with rotation_map for is_common
        rot_map = {r.abbrev: r for r in session.query(RotationMap).all()}

        result = []
        for rot, rot_full in rotations:
            is_common = rot_map[rot].is_common if rot in rot_map else 0
            result.append(
                {"rotation": rot, "rotation_full": rot_full, "is_common": is_common}
            )

        # Sort: common first, then alphabetical by full name
        result.sort(key=lambda x: (-x["is_common"], x["rotation_full"]))
        return result
    finally:
        session.close()


def get_all_resident_names() -> pd.DataFrame:
    session = get_session()
    try:
        residents = (
            session.query(
                Schedule.pgy,
                Schedule.name,
                Schedule.is_visiting,
                Schedule.visiting_institution,
            )
            .group_by(Schedule.pgy, Schedule.name)
            .order_by(Schedule.name)
            .all()
        )
        return pd.DataFrame(
            [
                {
                    "PGY": str(r.pgy),
                    "name": r.name,
                    "is_visiting": r.is_visiting,
                    "visiting_institution": r.visiting_institution,
                }
                for r in residents
            ]
        )
    finally:
        session.close()


def _entries_to_dataframe(entries: list[Schedule]) -> pd.DataFrame:
    """Convert ORM schedule entries to a DataFrame."""
    records = []
    for e in entries:
        vac_info = ""
        if e.vacations:
            vac_parts = []
            for v in e.vacations:
                label = "Vac" if v.vac_type == "vacation" else "Conf"
                status = f" ({v.approved_status})" if v.approved_status else ""
                vac_parts.append(f"{label}: {v.vac_start}-{v.vac_end}{status}")
            vac_info = "; ".join(vac_parts)

        rotation_display = e.rotation_full or e.rotation
        if e.location:
            rotation_display = f"{rotation_display} ({e.location})"

        records.append(
            {
                "PGY": e.pgy,
                "name": e.name,
                "rotation": rotation_display,
                "start_date": pd.Timestamp(e.start_date),
                "end_date": pd.Timestamp(e.end_date),
                "vacation_info": vac_info,
                "is_visiting": e.is_visiting,
                "visiting_institution": e.visiting_institution,
            }
        )
    return pd.DataFrame(records)


def prepare_table(df: pd.DataFrame) -> str:
    result = df.copy()

    result["Starting"] = result["start_date"].dt.strftime("%B %d")
    result["Until"] = result["end_date"].dt.strftime("%B %d")

    # Build display columns
    columns = ["Resident Name", "Rotation", "Starting", "Until"]

    result = result.rename({"name": "Resident Name", "rotation": "Rotation"}, axis=1)

    # Add vacation column if any entries have vacation info
    if "vacation_info" in result.columns and result["vacation_info"].any():
        result = result.rename({"vacation_info": "Vacation/Conf"}, axis=1)
        columns.append("Vacation/Conf")

    result = result[columns]
    return result.to_html(index=False, classes=["table", "table-striped"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, include_visiting: bool = True):
    schedule_data = get_data_from_date(include_visiting=include_visiting)

    groups = []
    if not schedule_data.empty:
        groups = [
            {"df": prepare_table(df), "pgy": g}
            for g, df in schedule_data.groupby("PGY")
        ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "groups": groups,
            "header_text": "Current Schedule for Today",
            "include_visiting": include_visiting,
        },
    )


@app.get("/date/", response_class=HTMLResponse)
async def date_page(
    request: Request,
    date: str = Query(..., description="Date parameter"),
    include_visiting: bool = True,
):
    schedule_data = get_data_from_date(date, include_visiting=include_visiting)

    groups = []
    if not schedule_data.empty:
        groups = [
            {"df": prepare_table(df), "pgy": g}
            for g, df in schedule_data.groupby("PGY")
        ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "groups": groups,
            "header_text": f"Schedule for Date: {date}",
            "include_visiting": include_visiting,
        },
    )


@app.get("/date_picker/", response_class=HTMLResponse)
def date_picker(request: Request):
    return templates.TemplateResponse("date_picker.html", {"request": request})


@app.get("/rotation/", response_class=HTMLResponse)
def rotation_schedule(
    request: Request,
    rotation: str = Query(..., description="Rotation parameter"),
    include_visiting: bool = True,
):
    schedule_data = get_rotation_schedule(rotation, include_visiting=include_visiting)

    groups = []
    if not schedule_data.empty:
        groups = [
            {"df": prepare_table(df), "pgy": g}
            for g, df in schedule_data.groupby("PGY")
        ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "groups": groups,
            "header_text": f"Schedule for Rotation: {rotation}",
            "include_visiting": include_visiting,
        },
    )


@app.get("/resident/", response_class=HTMLResponse)
def resident_schedule(
    request: Request, name: str = Query(..., description="Name parameter")
):
    schedule_data = get_resident_schedule(name)

    groups = []
    if not schedule_data.empty:
        groups = [
            {"df": prepare_table(df), "pgy": g}
            for g, df in schedule_data.groupby("PGY")
        ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "groups": groups,
            "header_text": f"Schedule for Resident: {name}",
            "include_visiting": True,
        },
    )


@app.get("/rotation_picker/", response_class=HTMLResponse)
def rotation_picker(request: Request):
    rotation_list = get_all_rotation_names()

    return templates.TemplateResponse(
        "rotation_picker.html",
        {
            "request": request,
            "rotations": rotation_list,
        },
    )


@app.get("/resident_picker/", response_class=HTMLResponse)
def resident_picker(request: Request):
    resident_list = get_all_resident_names()

    name_list = {}
    for pgy in range(1, 6):
        pgy_df = resident_list[resident_list["PGY"] == str(pgy)]
        names = []
        for _, row in pgy_df.iterrows():
            entry = {"name": row["name"]}
            if row.get("is_visiting") and row.get("visiting_institution"):
                entry["visiting_institution"] = row["visiting_institution"]
            names.append(entry)
        name_list[f"pgy{pgy}"] = names

    return templates.TemplateResponse(
        "resident_picker.html",
        {
            "request": request,
            "names": name_list,
        },
    )
