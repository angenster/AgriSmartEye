"""
田块管理路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Field, OperationRecord
# schemas 与 models 同名（Field / OperationRecord），必须别名导入，
# 否则 ORM 类被 pydantic 模型覆盖，db.query(Field) 直接抛 ArgumentError。
from schemas import (
    FieldCreate, FieldUpdate, Field as FieldSchema,
    OperationRecordCreate, OperationRecord as OperationRecordSchema,
)
from routers.auth import get_current_user
from models import User as UserModel

router = APIRouter()


@router.get("/", response_model=List[FieldSchema])
def get_fields(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """获取田块列表"""
    fields = db.query(Field).filter(
        Field.owner_id == current_user.id
    ).offset(skip).limit(limit).all()
    return fields


@router.post("/", response_model=FieldSchema)
def create_field(
    field: FieldCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """创建田块"""
    db_field = Field(**field.dict(), owner_id=current_user.id)
    db.add(db_field)
    db.commit()
    db.refresh(db_field)
    return db_field


@router.get("/{field_id}", response_model=FieldSchema)
def get_field(
    field_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """获取田块详情"""
    field = db.query(Field).filter(
        Field.id == field_id,
        Field.owner_id == current_user.id
    ).first()
    if not field:
        raise HTTPException(status_code=404, detail="田块不存在")
    return field


@router.put("/{field_id}", response_model=FieldSchema)
def update_field(
    field_id: int,
    field_update: FieldUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """更新田块信息"""
    field = db.query(Field).filter(
        Field.id == field_id,
        Field.owner_id == current_user.id
    ).first()
    if not field:
        raise HTTPException(status_code=404, detail="田块不存在")

    for key, value in field_update.dict(exclude_unset=True).items():
        setattr(field, key, value)

    db.commit()
    db.refresh(field)
    return field


@router.delete("/{field_id}")
def delete_field(
    field_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """删除田块"""
    field = db.query(Field).filter(
        Field.id == field_id,
        Field.owner_id == current_user.id
    ).first()
    if not field:
        raise HTTPException(status_code=404, detail="田块不存在")

    db.delete(field)
    db.commit()
    return {"success": True, "message": "田块已删除"}


@router.post("/{field_id}/operations", response_model=OperationRecordSchema)
def create_operation(
    field_id: int,
    operation: OperationRecordCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """创建操作记录"""
    field = db.query(Field).filter(
        Field.id == field_id,
        Field.owner_id == current_user.id
    ).first()
    if not field:
        raise HTTPException(status_code=404, detail="田块不存在")

    db_operation = OperationRecord(
        field_id=field_id,
        type=operation.type,
        content=operation.content,
        operator=operation.operator,
    )
    db.add(db_operation)
    db.commit()
    db.refresh(db_operation)
    return db_operation


@router.get("/{field_id}/operations", response_model=List[OperationRecordSchema])
def get_operations(
    field_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """获取田块操作记录"""
    field = db.query(Field).filter(
        Field.id == field_id,
        Field.owner_id == current_user.id
    ).first()
    if not field:
        raise HTTPException(status_code=404, detail="田块不存在")

    operations = db.query(OperationRecord).filter(
        OperationRecord.field_id == field_id
    ).order_by(OperationRecord.created_at.desc()).all()
    return operations
