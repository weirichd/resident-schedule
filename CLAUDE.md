# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Resident schedule viewer for OSU Hospital. Imports rotation schedules from Excel into SQLite, then serves them via a FastAPI web app.

## Common Commands

```bash
# Install dependencies
poetry install

# Run dev server
poetry run uvicorn app.app:app --reload

# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov

# Code formatting, linting, type checking
poetry run black .
poetry run flake8
poetry run mypy app

# Parse Excel schedule into SQLite (Claude-powered)
python parse_schedule.py --file <excel_file.xlsx> --output <database.db>
python parse_schedule.py --file <file> --output <db> --year <year>    # override year
python parse_schedule.py --file <file> --output <db> --debug           # verbose output
python parse_schedule.py --file <file> --output <db> --dry-run         # parse without writing
python parse_schedule.py --file <file> --output <db> --model <model>   # override Claude model

# Docker build and run
docker build -t resident-schedule .
docker run --rm -p 8000:8000 resident-schedule
```

## Architecture

**Data flow:** Excel → `parse_schedule.py` (Claude API) → SQLite (`resident_schedule.db`) → FastAPI (`app/app.py`) → Jinja2 templates

**Database schema:** Three tables defined in `app/models.py` using SQLAlchemy ORM:
- `resident` — resident info (name, pgy, program, is_visiting, visiting_institution)
- `schedule` — rotation assignments (resident_id FK, start_date, end_date, rotation, location, is_elective)
- `vacation` — vacation/conference annotations (resident_id FK, vac_start, vac_end, vac_type)

**app/database.py:** Engine and session factory setup.

**app/app.py:** Single-file FastAPI app. All routes and ORM query functions live here. Key query functions: `get_data_from_date()`, `get_rotation_schedule()`, `get_resident_schedule()`. DataFrames are formatted to HTML via `prepare_table()`. Supports `include_visiting` filter on schedule endpoints.

**`parse_schedule.py`:** Standalone script at repo root. Reads Excel → converts to CSV → sends to Claude API → writes Schedule + Vacation rows to SQLite. Requires `ANTHROPIC_API_KEY` env var.

**Routes:** `/` (today's schedule), `/date/` (by date), `/rotation/` (by rotation), `/resident/` (by name). Each has a corresponding `_picker` route for selection UI. All schedule endpoints accept `?include_visiting=true|false`.

**Templates:** Bootstrap 3 with jQuery. Schedule data displayed in tabs by PGY level.

## Deployment

Deployed on **AWS Lightsail Containers** (us-east-2). DNS managed via GoDaddy for osuresidentschedule.com.

## Code Quality

Pre-commit hooks enforce: Black formatting, flake8 (max line 120), mypy, trailing whitespace, import ordering. See `.pre-commit-config.yaml`.
