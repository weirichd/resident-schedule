"""
Script which translates the Excel spreadsheet into the Sqlite database.

Things I had to change in the Excel sheet:
    * Added '5' in PGY column for Surgical Onc fellow and Urogyn fellow
    * Changed '1- Prelim' to '1-Prelim' (sim 2) in a few rows
    * Changed 'Date' to 'Dates' for PGY 5 to match the others
    * Deleted the legend
"""
import argparse

import pandas as pd
import sqlalchemy


parser = argparse.ArgumentParser(
    description="Translate an Excel sheet with the resident schedule to a sqlite3 database."
)
parser.add_argument("--file", "-f", type=str, help="Input *.xlsx file", required=True)
parser.add_argument(
    "--output", "-o", type=str, help="output_database file", required=True
)

args = parser.parse_args()

file = args.file
output = args.output

# Read in the Excel sheet
sheet = pd.read_excel(file, header=None)

# These are the only unique values that appear as date ranges.
# PGY 5 gets two columns per rotation in the sheet but only the first matters
dates_map = {
    "July": ("2020-07-01", "2020-08-31"),
    "September": ("2020-09-01", "2020-10-31"),
    "November": ("2020-11-01", "2020-12-31"),
    "January": ("2021-01-01", "2021-02-28"),
    "March": ("2021-03-01", "2021-04-30"),
    "May": ("2021-05-01", "2021-06-30"),
    "July 1 - Aug. 22": ("2020-07-01", "2020-08-22"),
    "Aug. 23 - Oct. 17": ("2020-08-23", "2020-10-17"),
    "Oct. 18 - Dec. 12": ("2020-10-18", "2020-12-12"),
    "Dec. 13 - Feb. 6": ("2020-12-13", "2021-02-06"),
    "Feb. 7 - Mar. 27": ("2021-02-07", "2021-03-27"),
    "Mar. 28 - May 15": ("2021-03-28", "2021-05-15"),
    "May 16 - June 30": ("2021-05-16", "2021-06-30"),
    "7/1-7/26": ("2020-07-01", "2020-07-26"),
    "7/27-8/23": ("2020-07-27", "2020-08-23"),
    "8/24-9/20": ("2020-08-24", "2020-09-20"),
    "9/21-10/18": ("2020-09-21", "2020-10-18"),
    "10/19-11/15": ("2020-10-19", "2020-11-15"),
    "11/16-12/13": ("2020-11-16", "2020-12-13"),
    "12/14-1/10": ("2020-12-14", "2021-01-10"),
    "1/11-2/7": ("2021-01-11", "2021-02-07"),
    "2/8-3/7": ("2021-02-08", "2021-03-07"),
    "3/8-4/4": ("2021-03-08", "2021-04-04"),
    "4/5-5/2": ("2021-04-05", "2021-05-02"),
    "5/3-5/30": ("2021-05-03", "2021-05-30"),
    "5/31-6/30": ("2021-05-31", "2021-06-30"),
}

dates_map_for_fellows = {
    "August": ("2020-08-01", "2020-08-31"),
    "January": ("2021-01-01", "2021-01-31"),
    "May": ("2021-05-01", "2021-05-31"),
}

dates_dataframe = pd.DataFrame(dates_map).T
dates_dataframe.columns = ["start_date", "end_date"]
dates_dataframe_for_fellows = pd.DataFrame(dates_map_for_fellows).T
dates_dataframe_for_fellows.columns = ["start_date", "end_date"]

# Build up the database row by row.
result = pd.DataFrame(columns=["name", "PGY", "rotation", "start_date", "end_date"])

for i, row in sheet.iterrows():
    dates_row_num = 0
    if row[1] == "Dates":
        dates_row_num = i
    elif str(row[0]) == "nan":  # One of the blank rows
        continue
    else:
        resident = pd.Series(data=row.values, index=sheet.iloc[dates_row_num].values)
        name = resident.iloc[1]
        pgy = resident.iloc[0]
        rotation = resident.iloc[2:].dropna()
        rotation.name = "rotation"

        print("Adding:", name)

        if "FELLOW" in name.upper():
            dates_df = dates_dataframe_for_fellows
        else:
            dates_df = dates_dataframe

        this_residents_rows = pd.merge(
            rotation, dates_df, left_index=True, right_index=True, how="left"
        )
        this_residents_rows["PGY"] = pgy
        this_residents_rows["name"] = name

        result = pd.concat([result, this_residents_rows], axis=0)


# Fix the date times
result = result.reset_index(drop=True)
result["start_date"] = pd.to_datetime(result["start_date"])
result["end_date"] = pd.to_datetime(result["end_date"])


# Output the database
conn = sqlalchemy.create_engine(f"sqlite:///{output}", echo=False)
result.to_sql("schedule", conn, if_exists="replace", index=False)

print("Done!")
