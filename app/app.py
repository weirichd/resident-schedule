import pandas as pd
import sqlalchemy
from flask import Flask
from flask import render_template


app = Flask(__name__)


engine = sqlalchemy.create_engine("sqlite:///resident_schedule.db")
con = engine.connect()


query = """
select
    PGY,
    Name,
    Rotation,
    end_date
from schedule
where
DATE('now') between DATE(start_date) and DATE(end_date)
"""


schedule_data = pd.read_sql(con=con, sql=query, parse_dates=["end_date"])
schedule_data["Until"] = schedule_data["end_date"].dt.strftime("%B %d")


@app.route("/", methods=["GET"])
def home():
    global schedule_data

    def prepare_table(df):
        return df.drop(["PGY", "end_date"], axis=1).to_html(
            index=False, classes=["table", "table-striped"]
        )

    groups = [
        {"df": prepare_table(df), "pgy": g} for g, df in schedule_data.groupby("PGY")
    ]

    return render_template("templates.html", groups=groups)


if __name__ == "__main__":
    app.run(debug=True, port=8000, host="0.0.0.0")
