"""
智农慧眼后端API服务
FastAPI + SQLAlchemy + PostgreSQL + Redis
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import engine, Base
from routers import auth, detection, fields, drone, analysis, knowledge

# 创建数据库表
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("[START] 智农慧眼API服务启动中...")
    yield
    print("[STOP] 智农慧眼API服务已关闭")


app = FastAPI(
    title="智农慧眼API",
    description="基于AI视觉识别的热带作物病虫害精准防治系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(detection.router, prefix="/api/v1/detection", tags=["病虫害识别"])
app.include_router(fields.router, prefix="/api/v1/fields", tags=["田块管理"])
app.include_router(drone.router, prefix="/api/v1/drone", tags=["无人机控制"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["数据分析"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["知识库"])

# 静态文件
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
async def root():
    return {
        "name": "智农慧眼API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)