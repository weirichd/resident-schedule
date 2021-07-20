"""
Script which translates the Excel spreadsheet into the Sqlite database.
"""
import argparse

import pandas as pd
import sqlalchemy
import numpy as np

def clean_rotation_name(name):
    """Fix some common mistakes in the name in the excel sheet."""
    name = name.strip()
    
    if 'VAC' in name:
        # "VAC" means they are on vacation. I don't track this in the app.
        first, second = name.split('/')
        new_name = first if 'VAC' in second else second
        name = new_name
    
    return name


def handle_resident_row(row: pd.Series) -> pd.DataFrame:
    """Read a line of the CSV and return the tidy rows for the database"""
    name = row['Name']
    pgy = row['PGY']

    rotations = row.iloc[2:].dropna()
    rotations.name = 'rotation'
    rotations = rotations.reset_index()

    rotations['name'] = name
    rotations['PGY'] = pgy

    rotations['start_date'] = rotations['index'].apply(lambda x: x.split('-')[0])
    rotations['end_date'] = rotations['index'].apply(lambda x: x.split('-')[1])
    rotations['start_date'] = pd.to_datetime(rotations['start_date'])
    rotations['end_date'] = pd.to_datetime(rotations['end_date'])

    rotations['rotation'] = rotations['rotation'].apply(clean_rotation_name)

    rotations = rotations.drop('index', axis=1)

    return rotations


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Translate an Excel sheet with the resident schedule to a sqlite3 database."
    )
    parser.add_argument("--file", "-f", type=str, help="Input *.xlsx file", required=True)
    parser.add_argument(
        "--output", "-o", type=str, help="output_database file", required=True
    )

    args = parser.parse_args()

    file_path = args.file
    output = args.output

    # Read in the CSV sheet
    sheet = pd.read_csv(file_path)

    # Build up the database row by row.
    result = pd.DataFrame(columns=["name", "PGY", "rotation", "start_date", "end_date"])

    for _, row in sheet.iterrows():
        result = result.append(handle_resident_row(row)) 

    # Output the database
    conn = sqlalchemy.create_engine(f"sqlite:///{output}", echo=False)
    result.to_sql("schedule", conn, if_exists="replace", index=False)

    print("Done!")

