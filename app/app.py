from typing import Optional

import pandas as pd
import sqlalchemy
from flask import Flask
from flask import render_template
from flask import request


app = Flask(__name__)


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
    """

    return pd.read_sql(
        con=get_connection(), sql=query, parse_dates=["start_date", "end_date"]
    )


def get_all_rotation_names() -> pd.DataFrame:
    query = "select rotation from schedule group by 1 order by 1;"
    return pd.read_sql(con=get_connection(), sql=query)


def get_all_resident_names() -> pd.DataFrame:
    query = "select PGY, name from schedule group by 1, 2;"
    return pd.read_sql(con=get_connection(), sql=query)


def prepare_table(df):
    result = df.copy()

    result["Starting"] = result["start_date"].dt.strftime("%B %d")
    result["Until"] = result["end_date"].dt.strftime("%B %d")
    result = result.drop(["PGY", "start_date", "end_date"], axis=1, errors="ignore")
    result = result.rename({"name": "Resident Name", "rotation": "Rotation"}, axis=1)

    return result.to_html(index=False, classes=["table", "table-striped"])


@app.route("/", methods=["GET"])
def home():
    schedule_data = get_data_from_date()

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return render_template(
        "home.html", groups=groups, header_text="Current Schedule for Today"
    )


@app.route("/date/", methods=["GET"])
def date_page():
    date = request.args.get("date", type=str)

    schedule_data = get_data_from_date(date)

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return render_template(
        "home.html", groups=groups, header_text=f"Schedule for Date: {date}"
    )


@app.route("/date_picker/", methods=["GET"])
def date_picker():
    return render_template("date_picker.html")


@app.route("/rotation/", methods=["GET"])
def rotation_schedule():
    rotation = request.args.get("rotation", type=str)

    schedule_data = get_rotation_schedule(rotation)

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return render_template(
        "home.html", groups=groups, header_text=f"Schedule for Rotation: {rotation}"
    )


@app.route("/rotation_picker/", methods=["GET"])
def rotation_picker():
    rotation_list = get_all_rotation_names()

    return render_template(
        "rotation_picker.html", rotations=rotation_list["rotation"].to_list()
    )


if __name__ == "__main__":
    app.run(debug=True, port=8000, host="0.0.0.0")
