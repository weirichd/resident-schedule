from flask import Flask

import sqlalchemy

import pandas as pd


app = Flask(__name__)


engine = sqlalchemy.create_engine('sqlite:///resident_schedule.db')
con = engine.connect()


schedule_data = pd.read_sql(con=con, sql='select * from schedule', parse_dates=['start_date', 'end_date'])


@app.route("/", methods=["GET"])
def home():
    global schedule_data

    day = pd.Timestamp.today()

    result = ""
    for g, df in schedule_data.groupby('PGY'):
        today = df[(df['start_date'] <= day) & (day <= df['end_date'])]

        result += f'<H1>PGY {g}</h1>'
        result += today[['Name', 'Rotation', 'end_date']].rename({'end_date': 'Until'}, axis=1).to_html(index=False)
        result += '\n'

    return result


if __name__ == "__main__":
    app.run(debug=True)