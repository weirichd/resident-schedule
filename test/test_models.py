"""Tests for database models and schema."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Resident, Schedule, Vacation


def _make_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_schema_creation():
    """Schema creates without errors in an in-memory database."""
    engine = _make_engine()
    inspector = engine.dialect.get_table_names(engine.connect())
    assert "resident" in inspector
    assert "schedule" in inspector
    assert "vacation" in inspector


def test_insert_and_query_schedule():
    """Can insert and query schedule entries via resident."""
    engine = _make_engine()
    session = Session(engine)

    resident = Resident(
        name="Test Resident",
        pgy=3,
        program="General Surgery",
    )
    session.add(resident)
    session.flush()

    entry = Schedule(
        resident_id=resident.id,
        start_date="2025-07-01",
        end_date="2025-08-24",
        rotation="Acute Care Surgery",
        location=None,
    )
    session.add(entry)
    session.commit()

    result = session.query(Schedule).first()
    assert result is not None
    assert result.rotation == "Acute Care Surgery"
    assert result.resident.name == "Test Resident"
    assert result.resident.pgy == 3
    session.close()


def test_vacation_relationship():
    """Vacation entries link to residents."""
    engine = _make_engine()
    session = Session(engine)

    resident = Resident(
        name="Test Resident",
        pgy=5,
        program="General Surgery",
    )
    session.add(resident)
    session.flush()

    entry = Schedule(
        resident_id=resident.id,
        start_date="2025-07-01",
        end_date="2025-08-24",
        rotation="Colorectal Surgery",
    )
    session.add(entry)

    vac = Vacation(
        resident_id=resident.id,
        vac_start="2025-08-11",
        vac_end="2025-08-17",
        vac_type="vacation",
    )
    session.add(vac)
    session.commit()

    result = session.query(Resident).first()
    assert len(result.vacations) == 1
    assert result.vacations[0].vac_start == "2025-08-11"
    assert len(result.schedule_entries) == 1
    session.close()


def test_visiting_resident():
    """Visiting resident fields store correctly."""
    engine = _make_engine()
    session = Session(engine)

    resident = Resident(
        name="John Doe",
        pgy=4,
        program="General Surgery",
        is_visiting=1,
        visiting_institution="Doctors Hospital",
    )
    session.add(resident)
    session.flush()

    entry = Schedule(
        resident_id=resident.id,
        start_date="2025-11-17",
        end_date="2025-12-14",
        rotation="Transplant",
    )
    session.add(entry)
    session.commit()

    result = session.query(Resident).filter(Resident.is_visiting == 1).first()
    assert result.name == "John Doe"
    assert result.visiting_institution == "Doctors Hospital"
    assert len(result.schedule_entries) == 1
    session.close()
