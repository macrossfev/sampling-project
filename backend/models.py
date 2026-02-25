from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Text, Date, DateTime, ForeignKey,
)
from sqlalchemy.orm import relationship
from backend.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    short_name = Column(String(100))
    group_name = Column(String(200))
    address = Column(String(500))
    contact_person = Column(String(100))
    contact_phone = Column(String(50))
    trip_type = Column(String(20), default="single_day")  # single_day / two_day
    created_at = Column(DateTime, default=datetime.now)

    contracts = relationship("Contract", back_populates="company")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_no = Column(String(100), unique=True, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    year = Column(Integer)
    start_date = Column(Date)
    end_date = Column(Date)
    total_amount = Column(Float)
    full_analysis_months = Column(String(50), default="6,11")
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    company = relationship("Company", back_populates="contracts")
    water_plants = relationship(
        "WaterPlant", back_populates="contract", cascade="all, delete-orphan"
    )


class WaterPlant(Base):
    __tablename__ = "water_plants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    scale = Column(String(100))
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    sampling_points = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    contract = relationship("Contract", back_populates="water_plants")
    detection_items = relationship(
        "DetectionItem", back_populates="water_plant", cascade="all, delete-orphan"
    )


class DetectionItem(Base):
    __tablename__ = "detection_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    water_plant_id = Column(Integer, ForeignKey("water_plants.id"), nullable=False)
    sample_type = Column(String(100))
    detection_project = Column(String(200))
    detection_standard = Column(String(300))
    frequency_type = Column(String(20))
    frequency_value = Column(Integer, default=1)
    unit_price = Column(Float)
    annual_count = Column(Integer)
    subtotal = Column(Float)
    detection_level = Column(String(20))  # 常规 / 全分析
    created_at = Column(DateTime, default=datetime.now)

    water_plant = relationship("WaterPlant", back_populates="detection_items")
    tasks = relationship("SamplingTask", back_populates="detection_item")


class SamplingTrip(Base):
    __tablename__ = "sampling_trips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    group_no = Column(Integer, nullable=False)  # 1-4
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    trip_type = Column(String(20), default="single_day")  # single_day / two_day
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    route_notes = Column(Text)
    sampling_notes = Column(Text)
    status = Column(String(20), default="待安排")
    created_at = Column(DateTime, default=datetime.now)

    company = relationship("Company")


class SamplingTask(Base):
    __tablename__ = "sampling_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), default="contract")
    detection_item_id = Column(
        Integer, ForeignKey("detection_items.id"), nullable=True
    )
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    water_plant_name = Column(String(200))
    contract_no = Column(String(100))
    year = Column(Integer)
    month = Column(Integer)
    planned_date = Column(Date, nullable=True)
    sample_type = Column(String(100))
    detection_project = Column(String(200))
    detection_standard = Column(String(300))
    status = Column(String(20), default="待采样")
    actual_date = Column(Date, nullable=True)
    executor = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    trip_id = Column(Integer, ForeignKey("sampling_trips.id"), nullable=True)

    detection_item = relationship("DetectionItem", back_populates="tasks")
    company = relationship("Company")
    trip = relationship("SamplingTrip")
