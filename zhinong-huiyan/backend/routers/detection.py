"""
病虫害识别路由
"""
import os
import time
import uuid
import base64
from io import BytesIO
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from database import get_db
from models import DetectionRecord
from schemas import Detection, DetectionResponse, DetectionRequest
from routers.auth import get_current_user
from models import User

router = APIRouter()

# 模拟AI推理结果（实际生产环境加载真实模型）
MOCK_DETECTIONS = [
    {
        "crop_type": "芒果",
        "disease_name": "炭疽病",
        "confidence": 97.8,
        "severity": "中度",
        "bbox": [120, 80, 280, 220],
        "recommendation": "及时喷洒咪鲜胺或苯醚甲环唑，连续防治2-3次，间隔7-10天",
        "medicine": "45%咪鲜胺水乳剂",
        "dosage": "稀释1500-2000倍液",
    },
    {
        "crop_type": "芒果",
        "disease_name": "介壳虫",
        "confidence": 94.2,
        "severity": "轻度",
        "bbox": [320, 150, 420, 280],
        "recommendation": "在若虫盛发期喷施噻嗪酮或螺虫乙酯，注意轮换用药",
        "medicine": "25%噻嗪酮可湿性粉剂",
        "dosage": "稀释1000-1500倍液",
    },
]


@router.post("/upload", response_model=DetectionResponse)
async def detect_from_upload(
    file: UploadFile = File(...),
    crop_type: str = None,
    confidence_threshold: float = 0.85,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传图像进行病虫害识别"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传有效的图像文件")

    # 保存上传文件
    file_ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{file_ext}"
    upload_dir = "uploads/detections"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_name)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    # 模拟AI推理
    start_time = time.time()
    inference_time = (time.time() - start_time) * 1000  # ms

    results = []
    for detection_data in MOCK_DETECTIONS:
        if detection_data["confidence"] >= confidence_threshold * 100:
            record = DetectionRecord(
                user_id=current_user.id,
                image_path=file_path,
                crop_type=crop_type or detection_data["crop_type"],
                disease_name=detection_data["disease_name"],
                confidence=detection_data["confidence"],
                severity=detection_data["severity"],
                bbox=detection_data["bbox"],
                recommendation=detection_data["recommendation"],
                medicine=detection_data["medicine"],
                dosage=detection_data["dosage"],
                inference_time=inference_time,
            )
            db.add(record)
            results.append(record)

    db.commit()
    for r in results:
        db.refresh(r)

    return DetectionResponse(
        success=True,
        data=results,
        message=f"成功识别 {len(results)} 处病虫害，推理耗时 {inference_time:.1f}ms",
    )


@router.post("/base64", response_model=DetectionResponse)
async def detect_from_base64(
    request: DetectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Base64编码图像识别"""
    try:
        image_data = base64.b64decode(request.image_base64)
        image = Image.open(BytesIO(image_data))

        # 保存临时文件
        unique_name = f"{uuid.uuid4().hex}.jpg"
        upload_dir = "uploads/detections"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, unique_name)
        image.save(file_path)

        # 模拟推理
        start_time = time.time()
        inference_time = (time.time() - start_time) * 1000

        results = []
        for detection_data in MOCK_DETECTIONS:
            if detection_data["confidence"] >= request.confidence_threshold * 100:
                record = DetectionRecord(
                    user_id=current_user.id,
                    image_path=file_path,
                    crop_type=request.crop_type or detection_data["crop_type"],
                    disease_name=detection_data["disease_name"],
                    confidence=detection_data["confidence"],
                    severity=detection_data["severity"],
                    bbox=detection_data["bbox"],
                    recommendation=detection_data["recommendation"],
                    medicine=detection_data["medicine"],
                    dosage=detection_data["dosage"],
                    inference_time=inference_time,
                )
                db.add(record)
                results.append(record)

        db.commit()
        return DetectionResponse(
            success=True,
            data=results,
            message=f"识别完成，耗时 {inference_time:.1f}ms",
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图像解析失败: {str(e)}")


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
    ).with_entities(db.func.avg(DetectionRecord.confidence)).scalar() or 0

    today_count = db.query(DetectionRecord).filter(
        DetectionRecord.user_id == current_user.id,
        db.func.date(DetectionRecord.created_at) == db.func.current_date(),
    ).count()

    return {
        "total_detections": total,
        "today_count": today_count,
        "avg_confidence": round(avg_confidence, 2),
        "model_version": "v1.0",
    }
