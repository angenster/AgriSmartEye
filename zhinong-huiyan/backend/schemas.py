"""
Pydantic 数据模型定义 (请求/响应)
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from pydantic.fields import Field as PydanticField


# ============== 用户认证 ==============
class UserBase(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    organization: Optional[str] = None
    phone: Optional[str] = None


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


# ============== 田块管理 ==============
class FieldBase(BaseModel):
    name: str
    crop_type: str
    area: float
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class FieldCreate(FieldBase):
    pass


class FieldUpdate(BaseModel):
    name: Optional[str] = None
    crop_type: Optional[str] = None
    area: Optional[float] = None
    status: Optional[str] = None
    next_spray: Optional[datetime] = None


class Field(FieldBase):
    id: int
    status: str
    last_check: Optional[datetime] = None
    next_spray: Optional[datetime] = None
    created_at: datetime
    owner_id: int

    class Config:
        from_attributes = True


# ============== 操作记录 ==============
class OperationRecordBase(BaseModel):
    type: str
    content: str
    operator: Optional[str] = "系统"


class OperationRecordCreate(OperationRecordBase):
    field_id: int


class OperationRecord(OperationRecordBase):
    id: int
    field_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============== 病虫害识别 ==============
class DetectionBase(BaseModel):
    crop_type: Optional[str] = None
    disease_name: Optional[str] = None
    confidence: Optional[float] = None
    severity: Optional[str] = None
    bbox: Optional[List[float]] = None
    recommendation: Optional[str] = None
    medicine: Optional[str] = None
    dosage: Optional[str] = None


class DetectionCreate(DetectionBase):
    user_id: int
    field_id: Optional[int] = None
    image_path: str


class Detection(DetectionBase):
    id: int
    image_path: str
    inference_time: float
    model_version: str
    created_at: datetime

    class Config:
        from_attributes = True


class DetectionResponse(BaseModel):
    success: bool
    data: List[Detection]
    message: str


class DetectionRequest(BaseModel):
    image_base64: Optional[str] = None
    crop_type: Optional[str] = None
    confidence_threshold: float = PydanticField(default=0.85, ge=0.5, le=0.99)


# ============== 无人机 ==============
class DroneStatusBase(BaseModel):
    drone_id: str
    name: str
    battery: float
    altitude: float
    speed: float
    spray_rate: float
    latitude: float
    longitude: float
    status: str
    signal: float
    temperature: float


class DroneStatusResponse(DroneStatusBase):
    mission_progress: float
    is_variable_spray: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class DroneCommand(BaseModel):
    command: str = PydanticField(..., pattern="^(start|pause|return|emergency)$")
    variable_spray: Optional[bool] = None


# ============== 知识库 ==============
class PestInfoBase(BaseModel):
    name: str
    crop_type: str
    category: str
    symptoms: str
    causes: str
    prevention: List[str]
    treatment: List[str]
    severity: str
    season: List[str]


class PestInfoCreate(PestInfoBase):
    pass


class PestInfo(PestInfoBase):
    id: int
    image_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============== 数据分析 ==============
class SprayRecordBase(BaseModel):
    drone_id: str
    field_id: int
    area: float
    traditional_usage: float
    actual_usage: float
    saved_percentage: float
    date: datetime


class SprayRecord(SprayRecordBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisSummary(BaseModel):
    total_detections: int
    total_fields: int
    total_sprayed_area: float
    total_medicine_saved: float
    avg_confidence: float
    monthly_stats: List[dict]


# ============== 通用 ==============
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[dict]