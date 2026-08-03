"""
病虫害知识库路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import PestInfo
from schemas import PestInfoCreate, PestInfo

router = APIRouter()


@router.get("/", response_model=List[PestInfo])
def get_pest_list(
    crop_type: str = None,
    search: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """获取病虫害列表"""
    query = db.query(PestInfo)

    if crop_type:
        query = query.filter(PestInfo.crop_type == crop_type)

    if search:
        query = query.filter(
            (PestInfo.name.contains(search)) |
            (PestInfo.symptoms.contains(search))
        )

    pests = query.offset(skip).limit(limit).all()
    return pests


@router.get("/{pest_id}", response_model=PestInfo)
def get_pest(
    pest_id: int,
    db: Session = Depends(get_db),
):
    """获取病虫害详情"""
    pest = db.query(PestInfo).filter(PestInfo.id == pest_id).first()
    if not pest:
        raise HTTPException(status_code=404, detail="病虫害信息不存在")
    return pest


@router.post("/", response_model=PestInfo)
def create_pest(
    pest: PestInfoCreate,
    db: Session = Depends(get_db),
):
    """创建病虫害信息（管理员）"""
    db_pest = PestInfo(**pest.dict())
    db.add(db_pest)
    db.commit()
    db.refresh(db_pest)
    return db_pest


@router.get("/crops/types")
def get_crop_types(
    db: Session = Depends(get_db),
):
    """获取作物类型列表"""
    crops = db.query(PestInfo.crop_type).distinct().all()
    return [crop[0] for crop in crops]


@router.get("/stats/overview")
def get_knowledge_stats(
    db: Session = Depends(get_db),
):
    """获取知识库统计"""
    total_pests = db.query(PestInfo).count()
    total_crops = db.query(PestInfo.crop_type).distinct().count()
    total_images = db.query(PestInfo.image_count).scalar() or 0
    total_solutions = db.query(PestInfo).count()

    return {
        "total_pests": total_pests,
        "total_crops": total_crops,
        "total_images": total_images,
        "total_solutions": total_solutions,
    }
