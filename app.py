from flask import Flask

import sqlalchemy

import pandas as pd


app = Flask(__name__)


engine = sqlalchemy.create_engine('sqlite:///resident_schedule.db')
con = engine.connect()


query = """
select 
    PGY,
    Name, 
    Rotation, 
    end_date
from schedule
where
DATE('now') between start_date and end_date
"""


schedule_data = pd.read_sql(con=con, sql=query, parse_dates=['end_date'])
schedule_data['Until'] = schedule_data['end_date'].dt.strftime('%b %d')
schedule_data = schedule_data.drop('end_date', axis=1)


@app.route("/", methods=["GET"])
def home():
    global schedule_data

    result = ""
    for g, df in schedule_data.groupby('PGY'):
        result += f'<H1>PGY {g}</h1>'
        result += df.to_html(index=False)
        result += '\n'

    return result


if __name__ == "__main__":
    app.run(debug=True)
