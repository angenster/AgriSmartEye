"""
无人机控制路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import DroneStatus as DroneStatusModel
from schemas import DroneStatusResponse, DroneCommand
from routers.auth import get_current_user
from models import User

router = APIRouter()

# 模拟无人机数据
MOCK_DRONES = [
    {
        "drone_id": "ZN-001",
        "name": "智农一号",
        "battery": 78,
        "altitude": 12.5,
        "speed": 4.2,
        "spray_rate": 2.5,
        "latitude": 109.5,
        "longitude": 19.2,
        "status": "standby",
        "signal": 95,
        "temperature": 42,
        "mission_progress": 0,
        "is_variable_spray": True,
    },
    {
        "drone_id": "ZN-002",
        "name": "智农二号",
        "battery": 65,
        "altitude": 15.0,
        "speed": 5.1,
        "spray_rate": 3.0,
        "latitude": 109.52,
        "longitude": 19.22,
        "status": "flying",
        "signal": 88,
        "temperature": 45,
        "mission_progress": 35,
        "is_variable_spray": True,
    },
]


@router.get("/", response_model=List[DroneStatusResponse])
def get_drones(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取无人机列表"""
    drones = db.query(DroneStatusModel).all()
    if not drones:
        # 初始化模拟数据
        for drone_data in MOCK_DRONES:
            drone = DroneStatusModel(**drone_data)
            db.add(drone)
        db.commit()
        drones = db.query(DroneStatusModel).all()
    return drones


@router.get("/{drone_id}", response_model=DroneStatusResponse)
def get_drone(
    drone_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取无人机状态"""
    drone = db.query(DroneStatusModel).filter(
        DroneStatusModel.drone_id == drone_id
    ).first()
    if not drone:
        raise HTTPException(status_code=404, detail="无人机不存在")
    return drone


@router.post("/{drone_id}/command")
def send_command(
    drone_id: str,
    command: DroneCommand,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送无人机控制指令"""
    drone = db.query(DroneStatusModel).filter(
        DroneStatusModel.drone_id == drone_id
    ).first()
    if not drone:
        raise HTTPException(status_code=404, detail="无人机不存在")

    if command.command == "start":
        drone.status = "flying"
        drone.mission_progress = 0
    elif command.command == "pause":
        drone.status = "standby"
    elif command.command == "return":
        drone.status = "returning"
    elif command.command == "emergency":
        drone.status = "returning"
        drone.mission_progress = 0

    if command.variable_spray is not None:
        drone.is_variable_spray = command.variable_spray

    db.commit()
    db.refresh(drone)

    return {
        "success": True,
        "message": f"指令 '{command.command}' 已发送至 {drone_id}",
        "drone": drone,
    }


@router.get("/{drone_id}/mission")
def get_mission_status(
    drone_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取任务状态"""
    drone = db.query(DroneStatusModel).filter(
        DroneStatusModel.drone_id == drone_id
    ).first()
    if not drone:
        raise HTTPException(status_code=404, detail="无人机不存在")

    return {
        "drone_id": drone.drone_id,
        "status": drone.status,
        "progress": drone.mission_progress,
        "battery": drone.battery,
        "sprayed_area": drone.mission_progress * 0.5,
        "medicine_used": drone.mission_progress * 0.3,
        "estimated_remaining": max(0, 100 - drone.mission_progress) * 0.6,
    }
