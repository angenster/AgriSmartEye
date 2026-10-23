"""
病虫害识别路由

推理由 services.model_service 提供的进程内单例完成（真实 CNN 前向），
不再使用任何硬编码结果。治疗建议字段（recommendation / medicine / dosage）
在 P2 的 RAG 落地前一律留空 —— 按项目红线，药品与剂量只能来自检索到的知识片段，
不允许凭空生成。
"""
import os
import time
import uuid
import base64
from io import BytesIO
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from PIL import Image
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from database import get_db
from models import DetectionRecord
from schemas import Detection, DetectionResponse, DetectionRequest
from routers.auth import get_current_user
from models import User
from services.model_service import model_service, ModelNotAvailable

router = APIRouter()


def _save_upload(contents: bytes, ext: str) -> str:
    """把上传内容落盘到 uploads/detections，返回相对路径"""
    unique_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = "uploads/detections"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_name)
    with open(file_path, "wb") as f:
        f.write(contents)
    return file_path


def _build_record(result: dict, image_path: str, user_id: int, field_id=None) -> DetectionRecord:
    """把推理输出映射为 DetectionRecord。

    注意 bbox 恒为 None：TropicalPestNet 是图像级分类器，没有检测头，
    因此不产生目标框。README 与 mock 数据中曾出现的 bbox 是虚构的。
    """
    return DetectionRecord(
        user_id=user_id,
        field_id=field_id,
        image_path=image_path,
        crop_type=result["crop"]["name"],
        disease_name=result["disease"]["name"],
        confidence=result["disease"]["confidence"],
        severity=result["severity"]["name"],
        bbox=None,
        recommendation=None,
        medicine=None,
        dosage=None,
        model_version=model_service.model_version,
        inference_time=result["inference_time_ms"],
    )


def _low_confidence_note(confidence: float, threshold: float) -> str:
    """置信度低于阈值时的提示语。分类器总会给出一个答案，
    因此这里不静默丢弃结果，而是明确标注供下游（P1 的 Agent）决定是否升级 VLM。"""
    return (
        f"（注意：病害置信度 {confidence:.2f} 低于阈值 {threshold:.2f}，"
        "结果仅供参考，建议人工复核或升级多模态模型）"
    )


@router.post("/upload", response_model=DetectionResponse)
async def detect_from_upload(
    file: UploadFile = File(...),
    crop_type: str = None,
    confidence_threshold: float = 0.85,
    field_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传图像进行病虫害识别"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传有效的图像文件")

    file_ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    contents = await file.read()
    file_path = _save_upload(contents, file_ext)

    # 推理是 CPU 密集的阻塞调用，丢到线程池，避免堵住事件循环
    try:
        result = await run_in_threadpool(model_service.predict, file_path)
    except ModelNotAvailable as e:
        raise HTTPException(status_code=503, detail=f"推理服务不可用: {e}")

    record = _build_record(result, file_path, current_user.id, field_id)
    db.add(record)
    db.commit()
    db.refresh(record)

    message = f"识别完成，耗时 {result['inference_time_ms']:.1f}ms"
    if model_service.is_demo:
        message = "[DEMO 未训练模型] " + message
    if record.confidence < confidence_threshold:
        message += _low_confidence_note(record.confidence, confidence_threshold)

    return DetectionResponse(success=True, data=[record], message=message)


@router.post("/base64", response_model=DetectionResponse)
async def detect_from_base64(
    request: DetectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Base64编码图像识别"""
    if not request.image_base64:
        raise HTTPException(status_code=400, detail="缺少 image_base64 字段")

    try:
        image = Image.open(BytesIO(base64.b64decode(request.image_base64))).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图像解析失败: {str(e)}")

    # 先落盘再推理，保证响应里的 image_path 可回看
    buf = BytesIO()
    image.save(buf, format="JPEG")
    file_path = _save_upload(buf.getvalue(), ".jpg")

    try:
        result = await run_in_threadpool(model_service.predict, file_path)
    except ModelNotAvailable as e:
        raise HTTPException(status_code=503, detail=f"推理服务不可用: {e}")

    record = _build_record(result, file_path, current_user.id)
    db.add(record)
    db.commit()
    db.refresh(record)

    message = f"识别完成，耗时 {result['inference_time_ms']:.1f}ms"
    if model_service.is_demo:
        message = "[DEMO 未训练模型] " + message
    if record.confidence < request.confidence_threshold:
        message += _low_confidence_note(record.confidence, request.confidence_threshold)

    return DetectionResponse(success=True, data=[record], message=message)


@router.get("/history", response_model=List[Detection])
async def get_detection_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取识别历史"""
    records = (
        db.query(DetectionRecord)
        .filter(DetectionRecord.user_id == current_user.id)
        .order_by(DetectionRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return records


@router.get("/stats")
async def get_detection_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取识别统计"""
    total = db.query(DetectionRecord).filter(
        DetectionRecord.user_id == current_user.id
    ).count()

    avg_confidence = db.query(DetectionRecord).filter(
        DetectionRecord.user_id == current_user.id
    ).with_entities(func.avg(DetectionRecord.confidence)).scalar() or 0

    today_count = db.query(DetectionRecord).filter(
        DetectionRecord.user_id == current_user.id,
        func.date(DetectionRecord.created_at) == func.current_date(),
    ).count()

    return {
        "total_detections": total,
        "today_count": today_count,
        "avg_confidence": round(avg_confidence, 4),
        "model_version": model_service.model_version,
        "is_demo": model_service.is_demo,
    }
