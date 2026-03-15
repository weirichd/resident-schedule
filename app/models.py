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
    is_general_surgery = Column(Integer, default=0)

    vacations = relationship("Vacation", back_populates="schedule_entry")


class Vacation(Base):
    __tablename__ = "vacation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("schedule.id"), nullable=False)
    vac_start = Column(Text, nullable=False)
    vac_end = Column(Text, nullable=False)
    vac_type = Column(Text, default="vacation")

    schedule_entry = relationship("Schedule", back_populates="vacations")
