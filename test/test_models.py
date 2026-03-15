"""Tests for database models and schema."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Schedule, Vacation


def _make_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_schema_creation():
    """Schema creates without errors in an in-memory database."""
    engine = _make_engine()
    # Verify tables exist
    inspector = engine.dialect.get_table_names(engine.connect())
    assert "schedule" in inspector
    assert "vacation" in inspector


def test_insert_and_query_schedule():
    """Can insert and query schedule entries."""
    engine = _make_engine()
    session = Session(engine)

    entry = Schedule(
        start_date="2025-07-01",
        end_date="2025-08-24",
        name="Test Resident",
        pgy=3,
        rotation="ACS",
        rotation_full="Acute Care Surgery",
        location=None,
        is_visiting=0,
    )
    session.add(entry)
    session.commit()

    result = session.query(Schedule).filter(Schedule.name == "Test Resident").first()
    assert result is not None
    assert result.rotation == "ACS"
    assert result.rotation_full == "Acute Care Surgery"
    assert result.pgy == 3
    session.close()


def test_vacation_relationship():
    """Vacation entries link to schedule entries."""
    engine = _make_engine()
    session = Session(engine)

    entry = Schedule(
        start_date="2025-07-01",
        end_date="2025-08-24",
        name="Test Resident",
        pgy=5,
        rotation="CRS",
        rotation_full="Colorectal Surgery",
    )
    session.add(entry)
    session.flush()

    vac = Vacation(
        schedule_id=entry.id,
        vac_start="8/11",
        vac_end="8/17",
        vac_type="vacation",
    )
    session.add(vac)
    session.commit()

    result = session.query(Schedule).first()
    assert len(result.vacations) == 1
    assert result.vacations[0].vac_start == "8/11"
    session.close()


def test_visiting_resident():
    """Visiting resident fields store correctly."""
    engine = _make_engine()
    session = Session(engine)

    entry = Schedule(
        start_date="2025-11-17",
        end_date="2025-12-14",
        name="John Doe",
        pgy=4,
        rotation="Transplant",
        rotation_full="Transplant Surgery",
        is_visiting=1,
        visiting_institution="Doctors Hospital",
    )
    session.add(entry)
    session.commit()

    result = session.query(Schedule).filter(Schedule.is_visiting == 1).first()
    assert result.name == "John Doe"
    assert result.visiting_institution == "Doctors Hospital"
    session.close()
