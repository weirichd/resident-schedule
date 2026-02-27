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

# Import Excel schedule into SQLite (automated parser)
poetry run python -m app.parser.cli --file <excel_file.xlsx> --output <database.db> [--year <year>]
poetry run python -m app.parser.cli --file <file> --output <db> --debug    # verbose output
poetry run python -m app.parser.cli --file <file> --output <db> --dry-run  # parse without writing

# Docker build and run
./build.sh [tag]    # builds image, defaults to 'latest'
./run_docker.sh     # runs on port 8000

# Deploy (parse, test, build, push to Lightsail)
./deploy.sh <excel_file.xlsx>
```

## Architecture

**Data flow:** Excel → `app/parser/` → SQLite (`resident_schedule.db`) → FastAPI (`app/app.py`) → Jinja2 templates

**Database schema:** Three tables defined in `app/models.py` using SQLAlchemy ORM:
- `schedule` — rotation assignments (name, pgy, rotation, rotation_full, location, is_visiting, visiting_institution)
- `vacation` — vacation/conference annotations linked to schedule entries via schedule_id FK
- `rotation_map` — abbreviation→full name mappings with common/uncommon classification

**app/database.py:** Engine and session factory setup.

**app/app.py:** Single-file FastAPI app. All routes and ORM query functions live here. Key query functions: `get_data_from_date()`, `get_rotation_schedule()`, `get_resident_schedule()`. DataFrames are formatted to HTML via `prepare_table()`. Supports `include_visiting` filter on schedule endpoints.

**Parser module (`app/parser/`):**
- `rotation_map.py` — abbreviation mappings, compound rotation set, common/uncommon classification
- `layout_detector.py` — auto-detect column positions (name, PGY, rotation start) from Excel files
- `row_classifier.py` — classify rows as date, resident, vacation annotation, section header, or skip
- `cell_parser.py` — parse vacation annotations, "/" split rotations, East location, visiting residents
- `excel_parser.py` — main orchestrator that ties detection, classification, and parsing together
- `cli.py` — CLI entry point

**Routes:** `/` (today's schedule), `/date/` (by date), `/rotation/` (by rotation), `/resident/` (by name). Each has a corresponding `_picker` route for selection UI. All schedule endpoints accept `?include_visiting=true|false`.

**Templates:** Bootstrap 3 with jQuery. Schedule data displayed in tabs by PGY level.

## Code Quality

Pre-commit hooks enforce: Black formatting, flake8 (max line 120), mypy, trailing whitespace, import ordering. See `.pre-commit-config.yaml`.
