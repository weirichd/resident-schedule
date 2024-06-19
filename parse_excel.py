from typing import Tuple

import pandas as pd
import argparse
import sqlalchemy


def parse_date(s: str, year: int) -> pd.Timestamp:
    month, day = s.split("/")
    month, day = int(month), int(day)

    if month <= 6:
        year = year + 1

    return pd.Timestamp(year, month, day)


def parse_date_range(s: str, year: int) -> Tuple[pd.Timestamp, pd.Timestamp]:
    start, end = s.split("-")

    return parse_date(start, year), parse_date(end, year)


def handle_date_row(row: pd.Series, year: int) -> pd.DataFrame:
    """
    Read in a row of the table and parse it as a date row.
    """
    
    row = row.iloc[2:].dropna()
    dates = row.apply(lambda x: parse_date_range(x, year)).tolist()
    
    result = pd.DataFrame(dates)

    result.columns = ['start_date', 'end_date']

    return result


def handle_resident_row(row: pd.Series, dates: pd.DataFrame):
    result = dates.copy()
    result['name'] = row.iloc[1].strip()
    result['PGY'] = str(row.iloc[0])
    rotation = row.iloc[2:].reset_index(drop=True)
    rotation = rotation[:dates.shape[0]].strip()
    result['rotation'] = rotation
    result = result.dropna()

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Translate an Excel sheet with the resident schedule to a sqlite3 database."
    )
    parser.add_argument(
        "--file", "-f", type=str, help="Input *.xlsx file", required=True
    )
    parser.add_argument(
        "--output", "-o", type=str, help="output_database file", required=True
    )
    parser.add_argument("--year", type=int, help="What year is it?")

    args = parser.parse_args()

    file_path = args.file
    output = args.output
    year = args.year

    if year is None:
        print("Assuming you want the current year")
        year = pd.Timestamp.today().year
        print(f"{year=}")

    df = pd.read_excel(file_path)
    df.columns = range(df.columns.size)
    # Remove these annoying guys
    for col in df:
        df.loc[df[col] == '\xa0', col] = None

    print("Read this sheet")
    print(df)

    final_table_list = []

    # We iterate over the file and parse each line one at a time
    current_date_data = None
    for _, row in df.iterrows():
        print('-' * 20)
        print("Handle row:")
        print()
        print(row)

        print()
        action = input("(s)kip, (d)ate, (r)esident, (q)uit: ")

        if action == "d":
            print("Parseing as a date row")
            current_date_data = handle_date_row(row, year)
            
            print('Updating current date data:')
            print(current_date_data)

        elif action == "r":
            print("Parsing as a resident row")
            resident_data = handle_resident_row(row, current_date_data)
            print('Parsed data:')
            print(resident_data)
            final_table_list.append(resident_data)

        elif action == 'q':
            print('Bye!')
            exit()
        else:
            print("Skipping row")

    print('Finished!')
    print('Outputting database')

    result = pd.concat(final_table_list)

    conn = sqlalchemy.create_engine(f"sqlite:///{output}", echo=False)
    result.to_sql("schedule", conn, if_exists="replace", index=False)

    print('Done!')
