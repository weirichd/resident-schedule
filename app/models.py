from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Resident(Base):
    __tablename__ = "resident"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    pgy = Column(Integer, nullable=False)
    program = Column(Text, nullable=False, default="General Surgery")
    is_visiting = Column(Integer, default=0)
    visiting_institution = Column(Text, nullable=True)
    is_prelim = Column(Integer, default=0)
    is_name = Column(Integer, default=1)

    schedule_entries = relationship("Schedule", back_populates="resident")
    vacations = relationship("Vacation", back_populates="resident")


class Schedule(Base):
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resident_id = Column(Integer, ForeignKey("resident.id"), nullable=False)
    start_date = Column(Text, nullable=False)
    end_date = Column(Text, nullable=False)
    rotation = Column(Text, nullable=False)
    location = Column(Text, nullable=True)
    is_elective = Column(Integer, default=0)

    resident = relationship("Resident", back_populates="schedule_entries")


class Vacation(Base):
    __tablename__ = "vacation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resident_id = Column(Integer, ForeignKey("resident.id"), nullable=False)
    vac_start = Column(Text, nullable=False)
    vac_end = Column(Text, nullable=False)
    vac_type = Column(Text, default="vacation")

    resident = relationship("Resident", back_populates="vacations")
