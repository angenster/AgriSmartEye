"""
SQLAlchemy 数据模型定义
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum,
    UniqueConstraint,
)
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


class AgentRunStatus(PyEnum):
    running = "running"
    done = "done"
    needs_human = "needs_human"   # 证据矛盾 / 重度 / 高价值作物低置信，转人工
    truncated = "truncated"       # 步数耗尽，输出当前最佳草稿
    failed = "failed"


class AgentRun(Base):
    """一次诊断 Agent 运行。agent_steps 是它的全量轨迹，前端据此渲染思考过程时间线。"""
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    field_id = Column(Integer, ForeignKey("fields.id"), nullable=True)
    trigger = Column(String(50))            # upload / base64 / manual
    image_path = Column(String(500))
    status = Column(Enum(AgentRunStatus), default=AgentRunStatus.running)
    steps_used = Column(Integer, default=0)
    vlm_calls = Column(Integer, default=0)
    llm_tokens = Column(Integer, default=0)
    total_latency_ms = Column(Float)
    planner = Column(String(80))            # rule_based / llm:<model>
    report_json = Column(JSON)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    steps = relationship("AgentStep", back_populates="run", cascade="all, delete-orphan")


class AgentStep(Base):
    """Agent 的每一步：思考 → 工具调用 → 工具返回。"""
    __tablename__ = "agent_steps"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"))
    step_no = Column(Integer)
    thought = Column(Text)
    tool_name = Column(String(50))
    tool_args_json = Column(JSON)
    tool_result_json = Column(JSON)
    error = Column(Text)
    latency_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("AgentRun", back_populates="steps")


class SampleStatus(PyEnum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"


class SampleQueue(Base):
    """数据飞轮待复核队列（方案 §7.6）。

    入队样本来自"模型拿不准"的诊断：低置信、CNN 与 VLM 分歧、或 VLM 自身低置信。
    复核确认后的标签是增量微调（P4）唯一的数据来源。
    """
    __tablename__ = "sample_queue"

    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String(500))
    image_hash = Column(String(64), index=True)   # 用于去重，同一张图不重复入队
    source = Column(String(50))                   # agent_run / detection_upload / manual
    run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=True)
    field_id = Column(Integer, ForeignKey("fields.id"), nullable=True)

    # 模型侧的预标注，供复核人参考
    crop_type = Column(String(50), nullable=True)
    cnn_top1 = Column(String(100))
    cnn_conf = Column(Float)
    cnn_topk_json = Column(JSON)
    vlm_pred = Column(String(100), nullable=True)
    vlm_conf = Column(Float, nullable=True)
    vlm_rationale = Column(Text, nullable=True)

    trigger_reason = Column(String(120))          # 多个原因用 | 连接
    status = Column(Enum(SampleStatus), default=SampleStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)

    confirmations = relationship("SampleConfirmation", back_populates="sample",
                                 cascade="all, delete-orphan")


class SampleConfirmation(Base):
    """复核结论。final_label 是飞轮真正产出的东西。"""
    __tablename__ = "sample_confirmations"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(Integer, ForeignKey("sample_queue.id"))
    final_label = Column(String(100))             # 训练用标签；reject 时为空
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirm_source = Column(String(20))           # adopt / correct / reject
    points = Column(Integer, default=0)           # 激励积分（演示用）
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sample = relationship("SampleQueue", back_populates="confirmations")


class ModelVersion(Base):
    """模型版本登记。切换版本 = 改推理引擎加载的权重路径 + 这里改 status。"""
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    version_tag = Column(String(80), unique=True, index=True)
    base_version = Column(String(80), nullable=True)
    lora_path = Column(String(500), nullable=True)
    weights_path = Column(String(500), nullable=True)
    train_desc = Column(Text, nullable=True)
    status = Column(String(30), default="candidate")   # candidate / production / archived
    eval_metrics_json = Column(JSON)
    promoted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    eval_runs = relationship("EvalRun", back_populates="model_version",
                             cascade="all, delete-orphan")


class EvalRun(Base):
    """一次评测记录，供门禁判定与版本追溯。"""
    __tablename__ = "eval_runs"

    id = Column(Integer, primary_key=True, index=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"))
    dataset_name = Column(String(200))
    metrics_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    model_version = relationship("ModelVersion", back_populates="eval_runs")


class PesticideEntry(Base):
    """农药登记条目 —— query_pesticide 的唯一数据源。

    红线：药品名称与剂量只能来自这里，禁止模型生成。因此每一行都必须带
    source 溯源信息；verified=False 的行是未校审样例，工具只返回药品名与
    登记信息，绝不下发 dosage（剂量错误比没有建议更危险）。
    """
    __tablename__ = "pesticide_registry"
    __table_args__ = (
        UniqueConstraint("crop_type", "disease_name", "product_name", "formulation",
                         name="uq_pesticide_entry"),
    )

    id = Column(Integer, primary_key=True, index=True)
    crop_type = Column(String(50), index=True, nullable=True)
    disease_name = Column(String(100), index=True, nullable=False)
    product_name = Column(String(200), nullable=False)
    active_ingredient = Column(String(200), nullable=True)
    formulation = Column(String(100), nullable=True)      # 剂型，如 水乳剂
    dosage = Column(String(200), nullable=True)           # 稀释倍数 / 亩用量
    safe_interval_days = Column(Integer, nullable=True)   # 安全间隔期
    registration_no = Column(String(100), nullable=True)  # 农药登记证号
    manufacturer = Column(String(200), nullable=True)
    source = Column(String(200), nullable=False)
    source_url = Column(String(500), nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)