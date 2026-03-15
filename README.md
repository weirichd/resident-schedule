# OSU Residents Schedule App

A small app I made to help keep track of the OSU Hospital resident schedule.

## Setup

```bash
poetry install
```

## Usage

### Import a Schedule

Clean up the Excel sheet first:
- Remove all sheets except the one you want to load
- Remove any extra columns (like a legend)

Then run the parser:

```bash
poetry run python -m app.parser.cli --file <schedule.xlsx> --output resident_schedule.db
```

### Run Locally

```bash
poetry run uvicorn app.app:app --reload
```

### Run with Docker

```bash
docker build -t resident-schedule .
docker run --rm -p 8000:8000 resident-schedule
```

## Deployment

Deployed on **AWS Lightsail Containers** in us-east-2. DNS is managed via GoDaddy for osuresidentschedule.com.

## TODO List

* Add Github actions to automatically deploy to AWS when pushed
* Make it easier to manipulate the database
