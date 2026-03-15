from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models import Resident, Schedule

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
        q = (
            session.query(Schedule)
            .join(Resident)
            .options(joinedload(Schedule.resident).joinedload(Resident.vacations))
        )

        if name:
            q = q.filter(Resident.name == name).order_by(Schedule.start_date)
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
            q = q.filter(Resident.is_visiting == 0)

        entries = q.all()
        return _entries_to_dicts(entries, query_date=date)
    finally:
        session.close()


def get_all_rotation_names() -> list[dict]:
    """Get all distinct rotation names, sorted alphabetically."""
    session = get_session()
    try:
        rotations = (
            session.query(Schedule.rotation)
            .filter(Schedule.rotation != "Vacation")
            .group_by(Schedule.rotation)
            .all()
        )

        result = [{"rotation": rot[0]} for rot in rotations]
        result.sort(key=lambda x: x["rotation"])
        return result
    finally:
        session.close()


def get_all_resident_names() -> list[dict]:
    session = get_session()
    try:
        residents = session.query(Resident).order_by(Resident.name).all()
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
        r = e.resident
        rotation_display = e.rotation
        if e.location:
            rotation_display = f"{rotation_display} ({e.location})"

        start = pd.Timestamp(e.start_date)
        end = pd.Timestamp(e.end_date)

        # Build vacation info from resident's vacations that overlap this entry
        vacations = []
        on_vacation = False
        for v in r.vacations:
            try:
                vs = pd.Timestamp(v.vac_start)
                ve = pd.Timestamp(v.vac_end)
            except (ValueError, TypeError):
                continue

            # Only include vacations that overlap this schedule entry
            if ve < start or vs > end:
                continue

            vac_entry = {
                "type": v.vac_type,
                "start": v.vac_start,
                "end": v.vac_end,
                "start_display": vs.strftime("%b %d"),
                "end_display": ve.strftime("%b %d"),
                "active": False,
            }

            if query_date:
                qd = pd.Timestamp(query_date)
                if vs <= qd <= ve:
                    on_vacation = True
                    vac_entry["active"] = True

            vacations.append(vac_entry)

        records.append(
            {
                "pgy": r.pgy,
                "name": r.name,
                "program": r.program,
                "rotation": rotation_display,
                "rotation_raw": e.rotation,
                "start_date": start.strftime("%B %d"),
                "end_date": end.strftime("%B %d"),
                "vacations": vacations,
                "on_vacation": on_vacation,
                "is_visiting": r.is_visiting,
                "visiting_institution": r.visiting_institution,
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


def get_coming_next_entries(
    rotation: str, after_date: str, include_visiting: bool = True
) -> list[dict]:
    """Get the next block of schedule entries for a rotation after the given date.

    Finds the earliest start_date for this rotation that begins after after_date,
    then returns all entries starting on that date.
    """
    session = get_session()
    try:
        # Find the earliest start_date after the given date for this rotation
        next_start = session.query(func.min(Schedule.start_date)).filter(
            Schedule.rotation == rotation,
            func.date(Schedule.start_date) > func.date(after_date),
        )
        if not include_visiting:
            next_start = next_start.join(Resident).filter(Resident.is_visiting == 0)
        next_start_date = next_start.scalar()

        if not next_start_date:
            return []

        # Get all entries for that rotation starting on that date
        q = (
            session.query(Schedule)
            .join(Resident)
            .options(joinedload(Schedule.resident).joinedload(Resident.vacations))
            .filter(
                Schedule.rotation == rotation,
                func.date(Schedule.start_date) == func.date(next_start_date),
            )
            .order_by(Schedule.start_date)
        )
        if not include_visiting:
            q = q.filter(Resident.is_visiting == 0)

        entries = q.all()
        return _entries_to_dicts(entries, query_date=next_start_date)
    finally:
        session.close()


@app.get("/rotation/{rotation_name}/", response_class=HTMLResponse)
@app.get("/rotation/{rotation_name}/{date}", response_class=HTMLResponse)
def rotation_detail(
    request: Request,
    rotation_name: str,
    date: str | None = None,
    include_visiting: bool = True,
):
    if date is None:
        date = pd.Timestamp.now().strftime("%Y-%m-%d")

    entries = get_schedule_entries(date=date, include_visiting=include_visiting)
    current = [e for e in entries if e["rotation"].startswith(rotation_name)]
    current_groups = _group_by_pgy(current) if current else []

    coming_next = get_coming_next_entries(
        rotation_name, date, include_visiting=include_visiting
    )
    coming_next_groups = _group_by_pgy(coming_next) if coming_next else []

    display_date = pd.Timestamp(date).strftime("%B %d, %Y")

    return templates.TemplateResponse(
        "rotation_detail.html",
        {
            "request": request,
            "rotation_name": rotation_name,
            "display_date": display_date,
            "current_groups": current_groups,
            "coming_next_groups": coming_next_groups,
            "include_visiting": include_visiting,
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
        name_list[pgy_key] = [r for r in all_residents if r["pgy"] == str(pgy_num)]

    return templates.TemplateResponse(
        "resident_picker.html",
        {
            "request": request,
            "names": name_list,
        },
    )
