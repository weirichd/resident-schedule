from flask import Flask

import sqlalchemy

import pandas as pd


app = Flask(__name__)


engine = sqlalchemy.create_engine('sqlite:///resident_schedule.db')
con = engine.connect()


df = pd.read_sql(con=con, sql='select * from schedule')

print(df)


@app.route("/", methods=["GET"])
def home():
    global df

    return df.to_html()


if __name__ == "__main__":
    app.run(debug=True)