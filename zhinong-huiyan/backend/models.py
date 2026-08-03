"""
SQLAlchemy 数据模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum

from database import Base


class UserRole(PyEnum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    full_name = Column(String(100))
    role = Column(Enum(UserRole), default=UserRole.operator)
    organization = Column(String(200))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fields = relationship("Field", back_populates="owner")
    detections = relationship("DetectionRecord", back_populates="user")


class FieldStatus(PyEnum):
    healthy = "healthy"
    mild = "mild"
    moderate = "moderate"
    severe = "severe"


class Field(Base):
    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    crop_type = Column(String(50))
    area = Column(Float)
    location = Column(String(200))
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(Enum(FieldStatus), default=FieldStatus.healthy)
    owner_id = Column(Integer, ForeignKey("users.id"))
    last_check = Column(DateTime)
    next_spray = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="fields")
    operations = relationship("OperationRecord", back_populates="field")
    detections = relationship("DetectionRecord", back_populates="field")


class OperationType(PyEnum):
    ai_inspection = "ai_inspection"
    drone_spray = "drone_spray"
    manual_inspection = "manual_inspection"
    fertilize = "fertilize"
    irrigate = "irrigate"


class OperationRecord(Base):
    __tablename__ = "operation_records"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    type = Column(Enum(OperationType))
    content = Column(Text)
    operator = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    field = relationship("Field", back_populates="operations")


class DetectionRecord(Base):
    __tablename__ = "detection_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    field_id = Column(Integer, ForeignKey("fields.id"), nullable=True)
    image_path = Column(String(500))
    crop_type = Column(String(50))
    disease_name = Column(String(100))
    confidence = Column(Float)
    severity = Column(String(20))
    bbox = Column(JSON)
    recommendation = Column(Text)
    medicine = Column(String(500))
    dosage = Column(String(200))
    model_version = Column(String(50), default="v1.0")
    inference_time = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="detections")
    field = relationship("Field", back_populates="detections")


class DroneStatus(Base):
    __tablename__ = "drone_status"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(String(50), unique=True, index=True)
    name = Column(String(100))
    battery = Column(Float)
    altitude = Column(Float)
    speed = Column(Float)
    spray_rate = Column(Float)
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(String(50))
    signal = Column(Float)
    temperature = Column(Float)
    mission_progress = Column(Float, default=0)
    is_variable_spray = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SprayRecord(Base):
    __tablename__ = "spray_records"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(String(50))
    field_id = Column(Integer, ForeignKey("fields.id"))
    area = Column(Float)
    traditional_usage = Column(Float)
    actual_usage = Column(Float)
    saved_percentage = Column(Float)
    date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class PestInfo(Base):
    __tablename__ = "pest_info"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    crop_type = Column(String(50))
    category = Column(String(50))
    symptoms = Column(Text)
    causes = Column(Text)
    prevention = Column(JSON)
    treatment = Column(JSON)
    severity = Column(String(20))
    season = Column(JSON)
    image_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)