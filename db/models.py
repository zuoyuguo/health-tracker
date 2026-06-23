import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, Integer,
    Numeric, String, Text,
)
from sqlalchemy import DateTime
from sqlalchemy.types import JSON
from db.base import Base

# 用 JSON 代替 JSONB，SQLite 兼容（PostgreSQL 上 Alembic 迁移里单独用 JSONB）
_now = lambda: datetime.datetime.now(datetime.timezone.utc)


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    meal_type = Column(String(20))
    photo_url = Column(Text)
    foods = Column(JSON, nullable=False, default=list)
    total_calories = Column(Numeric(8, 2))
    protein_g = Column(Numeric(6, 2))
    carbs_g = Column(Numeric(6, 2))
    fat_g = Column(Numeric(6, 2))
    user_note = Column(Text)
    confirmed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)


class Sleep(Base):
    __tablename__ = "sleep"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sleep_date = Column(Date, nullable=False, unique=True)
    total_sleep_min = Column(Integer)
    deep_sleep_min = Column(Integer)
    light_sleep_min = Column(Integer)
    rem_sleep_min = Column(Integer)
    awake_min = Column(Integer)
    sleep_score = Column(Integer)
    hrv_avg = Column(Numeric(6, 2))
    resting_hr = Column(Integer)
    sleep_start = Column(DateTime(timezone=True))
    sleep_end = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_now)


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_date = Column(Date, nullable=False)
    activity_type = Column(String(50))
    duration_min = Column(Integer)
    calories_burned = Column(Numeric(8, 2))
    avg_hr = Column(Integer)
    max_hr = Column(Integer)
    steps = Column(Integer)
    distance_km = Column(Numeric(6, 3))
    hr_zone_1_min = Column(Integer)
    hr_zone_2_min = Column(Integer)
    hr_zone_3_min = Column(Integer)
    hr_zone_4_min = Column(Integer)
    hr_zone_5_min = Column(Integer)
    garmin_activity_id = Column(BigInteger, unique=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class BodyMetric(Base):
    __tablename__ = "body_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    measured_at = Column(DateTime(timezone=True), nullable=False)
    weight_kg = Column(Numeric(5, 2))
    bmi = Column(Numeric(5, 2))
    body_fat_pct = Column(Numeric(5, 2))
    fat_mass_kg = Column(Numeric(5, 2))
    lean_mass_kg = Column(Numeric(5, 2))
    muscle_mass_kg = Column(Numeric(5, 2))
    bone_mass_kg = Column(Numeric(5, 2))
    water_pct = Column(Numeric(5, 2))
    visceral_fat = Column(Numeric(5, 2))
    bmr_kcal = Column(Integer)
    renpho_record_id = Column(String(64), unique=True)
    created_at = Column(DateTime(timezone=True), default=_now)
