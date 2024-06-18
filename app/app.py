from typing import Optional

import pandas as pd
import sqlalchemy

from fastapi import FastAPI, Request, APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


app = FastAPI()
router = APIRouter()
templates = Jinja2Templates(directory='app/templates')


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


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    schedule_data = get_data_from_date()

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return templates.TemplateResponse("home.html", {"request": request, "groups": groups, "header_text": "Current Schedule for Today"})


app.include_router(router)


# 
# @app.route("/date/", methods=["GET"])
# def date_page():
#     date = request.args.get("date", type=str)
# 
#     schedule_data = get_data_from_date(date)
# 
#     groups = [
#         {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
#     ]
# 
#     return render_template(
#         "home.html", groups=groups, header_text=f"Schedule for Date: {date}"
#     )
# 
# 
# @app.route("/date_picker/", methods=["GET"])
# def date_picker():
#     return render_template("date_picker.html")
# 
# 
# @app.route("/rotation/", methods=["GET"])
# def rotation_schedule():
#     rotation = request.args.get("rotation", type=str)
# 
#     schedule_data = get_rotation_schedule(rotation)
# 
#     groups = [
#         {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
#     ]
# 
#     return render_template(
#         "home.html", groups=groups, header_text=f"Schedule for Rotation: {rotation}"
#     )
# 
# 
# @app.route("/resident/", methods=["GET"])
# def resident_schedule():
#     name = request.args.get("name", type=str)
# 
#     schedule_data = get_resident_schedule(name)
# 
#     groups = [
#         {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
#     ]
# 
#     return render_template(
#         "home.html", groups=groups, header_text=f"Full Schedule for {name}"
#     )
# 
# 
# @app.route("/rotation_picker/", methods=["GET"])
# def rotation_picker():
#     rotation_list = get_all_rotation_names()
# 
#     return render_template(
#         "rotation_picker.html", rotations=rotation_list["rotation"].to_list()
#     )
# 
# 
# @app.route("/resident_picker/", methods=["GET"])
# def resident_picker():
#     resident_list = get_all_resident_names()
# 
#     names = {
#         f"pgy{pgy}": resident_list[resident_list["PGY"] == str(pgy)]["name"].to_list()
#         for pgy in range(1, 6)
#     }
# 
#     return render_template("resident_picker.html", names=names)
# 
# 
# 
# 
# 
