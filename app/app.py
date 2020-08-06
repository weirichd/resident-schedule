from typing import Optional

import pandas as pd
import sqlalchemy
from flask import Flask
from flask import render_template
from flask import request


app = Flask(__name__)


def get_data_from_date(date: Optional[str] = None) -> str:
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

    engine = sqlalchemy.create_engine("sqlite:///resident_schedule.db")
    con = engine.connect()

    schedule_data = pd.read_sql(
        con=con, sql=query, parse_dates=["start_date", "end_date"]
    )
    schedule_data["Starting"] = schedule_data["start_date"].dt.strftime("%B %d")
    schedule_data["Until"] = schedule_data["end_date"].dt.strftime("%B %d")

    return schedule_data


def prepare_table(df):
    return df.drop(["PGY", "start_date", "end_date"], axis=1).to_html(
        index=False, classes=["table", "table-striped"]
    )


@app.route("/", methods=["GET"])
def home():
    schedule_data = get_data_from_date()

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return render_template("home.html", groups=groups)


@app.route("/date/", methods=["GET"])
def date_page():
    date = request.args.get("date", type=str)

    schedule_data = get_data_from_date(date)

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return render_template("date.html", groups=groups, selected_date=date)


@app.route("/date_picker/", methods=["GET"])
def date_picker():

    return render_template("date_picker.html")


if __name__ == "__main__":
    app.run(debug=True, port=8000, host="0.0.0.0")
