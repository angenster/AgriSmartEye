"""
数据分析路由
"""
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import DetectionRecord, SprayRecord, Field
from schemas import AnalysisSummary
from routers.auth import get_current_user
from models import User

router = APIRouter()


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取数据分析摘要"""
    total_detections = db.query(DetectionRecord).filter(
        DetectionRecord.user_id == current_user.id
    ).count()

    total_fields = db.query(Field).filter(
        Field.owner_id == current_user.id
    ).count()

    total_sprayed = db.query(func.sum(SprayRecord.area)).filter(
        SprayRecord.field_id.in_(
            db.query(Field.id).filter(Field.owner_id == current_user.id)
        )
    ).scalar() or 0

    total_saved = db.query(func.sum(
        SprayRecord.traditional_usage - SprayRecord.actual_usage
    )).filter(
        SprayRecord.field_id.in_(
            db.query(Field.id).filter(Field.owner_id == current_user.id)
        )
    ).scalar() or 0

    avg_conf = db.query(func.avg(DetectionRecord.confidence)).filter(
        DetectionRecord.user_id == current_user.id
    ).scalar() or 0

    # 月度统计
    monthly = []
    for i in range(6):
        month_start = datetime.utcnow().replace(day=1) - timedelta(days=i*30)
        month_end = month_start + timedelta(days=30)

        detections = db.query(DetectionRecord).filter(
            DetectionRecord.user_id == current_user.id,
            DetectionRecord.created_at >= month_start,
            DetectionRecord.created_at < month_end,
        ).count()

        sprayed = db.query(func.sum(SprayRecord.area)).filter(
            SprayRecord.date >= month_start,
            SprayRecord.date < month_end,
        ).scalar() or 0

        monthly.append({
            "month": month_start.strftime("%Y-%m"),
            "detections": detections,
            "sprayed_area": round(sprayed, 2),
        })

    return {
        "total_detections": total_detections,
        "total_fields": total_fields,
        "total_sprayed_area": round(total_sprayed, 2),
        "total_medicine_saved": round(total_saved, 2),
        "avg_confidence": round(avg_conf, 2),
        "monthly_stats": list(reversed(monthly)),
    }


@router.get("/cost-comparison")
def get_cost_comparison(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取成本对比数据"""
    months = []
    for i in range(6):
        month_start = datetime.utcnow().replace(day=1) - timedelta(days=i*30)
        month_name = month_start.strftime("%m月")

        records = db.query(SprayRecord).filter(
            SprayRecord.date >= month_start,
            SprayRecord.date < month_start + timedelta(days=30),
            SprayRecord.field_id.in_(
                db.query(Field.id).filter(Field.owner_id == current_user.id)
            ),
        ).all()

        traditional = sum(r.traditional_usage for r in records)
        actual = sum(r.actual_usage for r in records)
        saved = ((traditional - actual) / traditional * 100) if traditional > 0 else 0

        months.append({
            "month": month_name,
            "traditional": round(traditional, 1),
            "smart": round(actual, 1),
            "saved": round(saved, 1),
        })

    return list(reversed(months))


@router.get("/spray-records")
def get_spray_records(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取施药记录"""
    records = db.query(SprayRecord).filter(
        SprayRecord.field_id.in_(
            db.query(Field.id).filter(Field.owner_id == current_user.id)
        )
    ).order_by(SprayRecord.date.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "field_id": r.field_id,
            "drone_id": r.drone_id,
            "area": r.area,
            "traditional_usage": r.traditional_usage,
            "actual_usage": r.actual_usage,
            "saved_percentage": round(r.saved_percentage, 1),
            "date": r.date.strftime("%Y-%m-%d"),
        }
        for r in records
    ]


@router.get("/disease-distribution")
def get_disease_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取病虫害分布统计"""
    results = db.query(
        DetectionRecord.disease_name,
        func.count(DetectionRecord.id).label("count")
    ).filter(
        DetectionRecord.user_id == current_user.id
    ).group_by(DetectionRecord.disease_name).order_by(func.count(DetectionRecord.id).desc()).limit(10).all()

    return [
        {"name": name, "value": count}
        for name, count in results
    ]
