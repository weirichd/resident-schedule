from typing import Optional

import pandas as pd
import sqlalchemy

from fastapi import FastAPI, Request, APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


app = FastAPI()
templates = Jinja2Templates(directory="app/templates")


def get_connection():
    engine = sqlalchemy.create_engine("sqlite:///resident_schedule.db")
    con = engine.connect()
    return con


def get_data_from_date(date: Optional[str] = None) -> pd.DataFrame:
    if date is None:
        date = "now"

    query = f"""
    select
        PGY,
        Name,
        Rotation,
        start_date,
        end_date
    from schedule
    where
    DATE('{date}') between DATE(start_date) and DATE(end_date)
    """

    return pd.read_sql(
        con=get_connection(), sql=query, parse_dates=["start_date", "end_date"]
    )


def get_rotation_schedule(rotation: str) -> pd.DataFrame:
    query = f"""
    select
        PGY,
        Name,
        start_date,
        end_date
    from schedule
    where
    Rotation='{rotation}'
    order by start_date;
    """

    return pd.read_sql(
        con=get_connection(), sql=query, parse_dates=["start_date", "end_date"]
    )


def get_resident_schedule(name: str) -> pd.DataFrame:
    query = f"""
    select
        PGY,
        rotation,
        start_date,
        end_date
    from schedule
    where name = '{name}'
    order by start_date
    """

    return pd.read_sql(
        con=get_connection(), sql=query, parse_dates=["start_date", "end_date"]
    )


def get_all_rotation_names() -> pd.DataFrame:
    query = "select rotation from schedule group by 1 order by 1;"
    return pd.read_sql(con=get_connection(), sql=query)


def get_all_resident_names() -> pd.DataFrame:
    query = "select PGY, name from schedule group by 1, 2;"
    return pd.read_sql(con=get_connection(), sql=query).sort_values("name")


def prepare_table(df):
    result = df.copy()

    result["Starting"] = result["start_date"].dt.strftime("%B %d")
    result["Until"] = result["end_date"].dt.strftime("%B %d")
    result = result.drop(["PGY", "start_date", "end_date"], axis=1, errors="ignore")
    result = result.rename({"name": "Resident Name", "rotation": "Rotation"}, axis=1)

    return result.to_html(index=False, classes=["table", "table-striped"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    schedule_data = get_data_from_date()

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "groups": groups,
            "header_text": "Current Schedule for Today",
        },
    )


@app.get("/date/", response_class=HTMLResponse)
async def date_page(
    request: Request, date: str = Query(..., description="Date parameter")
):
    schedule_data = get_data_from_date(date)

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "groups": groups,
            "header_text": f"Schedule for Date: {date}",
        },
    )


@app.get("/date_picker/", response_class=HTMLResponse)
def date_picker(request: Request):
    return templates.TemplateResponse("date_picker.html", {"request": request})


@app.get("/rotation/", response_class=HTMLResponse)
def rotation_schedule(
    request: Request, rotation: str = Query(..., description="Rotation parameter")
):
    schedule_data = get_rotation_schedule(rotation)

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "groups": groups,
            "header_text": f"Schedule for Rotation: {rotation}",
        },
    )


@app.get("/resident/", response_class=HTMLResponse)
def resident_schedule(request: Request, name: str = Query(..., description="Name parameter")):
    schedule_data = get_resident_schedule(name)

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "groups": groups,
            "header_text": f"Schedule for Resident: {name}",
        },
    )


@app.get("/rotation_picker/", response_class=HTMLResponse)
def rotation_picker(request: Request):
    rotation_list = get_all_rotation_names()["rotation"].to_list()

    return templates.TemplateResponse(
        "rotation_picker.html",
        {
            "request": request,
            "rotations": rotation_list,
        },
    )


@app.route("/resident_picker/", methods=["GET"])
def resident_picker(request: Request):
    resident_list = get_all_resident_names()

    name_list = {
        f"pgy{pgy}": resident_list[resident_list["PGY"] == str(pgy)]["name"].to_list()
        for pgy in range(1, 6)
    }

    return templates.TemplateResponse(
        "resident_picker.html",
        {
            "request": request,
            "names": name_list,
        },
    )





