from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Schedule(Base):
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_date = Column(Text, nullable=False)
    end_date = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    pgy = Column(Integer, nullable=False)
    rotation = Column(Text, nullable=False)
    rotation_full = Column(Text, nullable=False)
    location = Column(Text, nullable=True)
    is_visiting = Column(Integer, default=0)
    visiting_institution = Column(Text, nullable=True)

    vacations = relationship("Vacation", back_populates="schedule_entry")


class Vacation(Base):
    __tablename__ = "vacation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("schedule.id"), nullable=False)
    vac_start = Column(Text, nullable=False)
    vac_end = Column(Text, nullable=False)
    vac_type = Column(Text, default="vacation")
    approved_status = Column(Text, nullable=True)
    covered_by = Column(Text, nullable=True)

    schedule_entry = relationship("Schedule", back_populates="vacations")


class RotationMap(Base):
    __tablename__ = "rotation_map"

    abbrev = Column(Text, primary_key=True)
    full_name = Column(Text, nullable=False)
    is_common = Column(Integer, default=0)
