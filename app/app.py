from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models import Schedule, RotationMap

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")


def get_session() -> Session:
    return SessionLocal()


def get_schedule_entries(
    date: Optional[str] = None,
    rotation: Optional[str] = None,
    name: Optional[str] = None,
    include_visiting: bool = True,
) -> list[dict]:
    """Query schedule entries and return structured dicts with vacation info.

    Exactly one of date, rotation, or name should be provided.
    """
    session = get_session()
    try:
        q = session.query(Schedule).options(joinedload(Schedule.vacations))

        if name:
            q = q.filter(Schedule.name == name).order_by(Schedule.start_date)
        elif rotation:
            q = q.filter(Schedule.rotation == rotation).order_by(Schedule.start_date)
        else:
            if date is None:
                date = pd.Timestamp.now().strftime("%Y-%m-%d")
            q = q.filter(
                func.date(date) >= func.date(Schedule.start_date),
                func.date(date) <= func.date(Schedule.end_date),
            )

        if not include_visiting and not name:
            q = q.filter(Schedule.is_visiting == 0)

        entries = q.all()
        return _entries_to_dicts(entries, query_date=date)
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
            .filter(Schedule.rotation != "VACATION")
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


def get_all_resident_names() -> list[dict]:
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
        return [
            {
                "pgy": str(r.pgy),
                "name": r.name,
                "is_visiting": r.is_visiting,
                "visiting_institution": r.visiting_institution,
            }
            for r in residents
        ]
    finally:
        session.close()


def _entries_to_dicts(
    entries: list[Schedule], query_date: Optional[str] = None
) -> list[dict]:
    """Convert ORM schedule entries to dicts with vacation awareness."""
    records = []
    for e in entries:
        rotation_display = e.rotation_full or e.rotation
        if e.location:
            rotation_display = f"{rotation_display} ({e.location})"

        start = pd.Timestamp(e.start_date)
        end = pd.Timestamp(e.end_date)

        # Build vacation info
        vacations = []
        on_vacation = False
        for v in e.vacations:
            vac_entry = {
                "type": v.vac_type,
                "start": v.vac_start,
                "end": v.vac_end,
                "status": v.approved_status,
                "covered_by": v.covered_by,
            }

            # Format display dates
            try:
                vs = pd.Timestamp(v.vac_start)
                ve = pd.Timestamp(v.vac_end)
                vac_entry["start_display"] = vs.strftime("%b %d")
                vac_entry["end_display"] = ve.strftime("%b %d")

                # Check if query date falls within this vacation
                if query_date:
                    qd = pd.Timestamp(query_date)
                    if vs <= qd <= ve:
                        on_vacation = True
                        vac_entry["active"] = True
                    else:
                        vac_entry["active"] = False
                else:
                    vac_entry["active"] = False
            except (ValueError, TypeError):
                # Fallback for M/D format dates (pre-migration)
                vac_entry["start_display"] = v.vac_start
                vac_entry["end_display"] = v.vac_end
                vac_entry["active"] = False

            vacations.append(vac_entry)

        records.append(
            {
                "pgy": e.pgy,
                "name": e.name,
                "rotation": rotation_display,
                "start_date": start.strftime("%B %d"),
                "end_date": end.strftime("%B %d"),
                "vacations": vacations,
                "on_vacation": on_vacation,
                "is_visiting": e.is_visiting,
                "visiting_institution": e.visiting_institution,
            }
        )
    return records


def _group_by_pgy(entries: list[dict]) -> list[dict]:
    """Group entries by PGY level for tabbed display."""
    from collections import defaultdict

    groups: dict[int, list[dict]] = defaultdict(list)
    for e in entries:
        groups[e["pgy"]].append(e)

    has_vacations = any(e["vacations"] for e in entries)

    return [
        {"pgy": pgy, "entries": groups[pgy], "has_vacations": has_vacations}
        for pgy in sorted(groups.keys())
    ]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, include_visiting: bool = True):
    entries = get_schedule_entries(include_visiting=include_visiting)
    groups = _group_by_pgy(entries)

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
    entries = get_schedule_entries(date=date, include_visiting=include_visiting)
    groups = _group_by_pgy(entries)

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
    entries = get_schedule_entries(rotation=rotation, include_visiting=include_visiting)
    groups = _group_by_pgy(entries)

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
    entries = get_schedule_entries(name=name)
    groups = _group_by_pgy(entries)

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
    all_residents = get_all_resident_names()

    name_list: dict[str, list[dict]] = {}
    for pgy_num in range(1, 6):
        pgy_key = f"pgy{pgy_num}"
        name_list[pgy_key] = [
            r for r in all_residents if r["pgy"] == str(pgy_num)
        ]

    return templates.TemplateResponse(
        "resident_picker.html",
        {
            "request": request,
            "names": name_list,
        },
    )
