"""
病虫害知识库路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import PestInfo
# schemas.PestInfo 与 models.PestInfo 同名：必须别名导入，否则 ORM 类被覆盖，
# db.query(PestInfo) 会抛 sqlalchemy ArgumentError。
from schemas import PestInfoCreate, PestInfo as PestInfoSchema

router = APIRouter()


@router.get("/", response_model=List[PestInfoSchema])
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


@router.get("/chunks")
def list_chunks(
    search: str = None,
    crop: str = None,
    limit: int = 50,
):
    """列出 RAG 索引中的知识条目（只读）。

    这才是系统当前实际使用的知识源：pest_info 表是历史遗留的结构化容器，
    而检索走的是 knowledge_chunks。此路由必须定义在 /{pest_id} 之前，
    否则 "/chunks" 会被单段路径参数当成 pest_id 解析。
    """
    from rag.store import connect, ensure_schema

    conn = connect()
    try:
        ensure_schema(conn)
        sql = "SELECT id, source, ref_id, title, text, metadata_json, created_at FROM knowledge_chunks"
        clauses, params = [], []
        if search:
            clauses.append("(title LIKE ? OR text LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if crop:
            clauses.append("title LIKE ?")
            params.append(f"%{crop}%")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id LIMIT ?"
        params.append(max(1, min(limit, 200)))

        rows = conn.execute(sql, params).fetchall()
        import json
        return [
            {
                "id": r["id"],
                "source": r["source"],
                "ref_id": r["ref_id"],
                "title": r["title"],
                "text": r["text"],
                "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {},
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


@router.get("/{pest_id}", response_model=PestInfoSchema)
def get_pest(
    pest_id: int,
    db: Session = Depends(get_db),
):
    """获取病虫害详情"""
    pest = db.query(PestInfo).filter(PestInfo.id == pest_id).first()
    if not pest:
        raise HTTPException(status_code=404, detail="病虫害信息不存在")
    return pest


@router.post("/", response_model=PestInfoSchema)
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
