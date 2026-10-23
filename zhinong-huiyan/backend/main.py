"""
智农慧眼后端API服务
FastAPI + SQLAlchemy + PostgreSQL + Redis
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from database import engine, Base
from routers import auth, detection, fields, drone, analysis, knowledge, agent, review
from services.model_service import model_service

# 创建数据库表
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("[START] 智农慧眼API服务启动中...")
    # 模型加载是阻塞且耗时数秒的，放到线程池以免拖住启动
    await run_in_threadpool(model_service.load)
    print(f"[MODEL] {model_service.describe()}")

    # RAG 重排模型预热（约 20s）。任何失败都不阻塞启动：
    # 检索会自动退化为 RRF 顺序，并在结果里标注 rerank_ok=false。
    try:
        from rag import retriever as rag_retriever
        from rag import store as rag_store

        conn = rag_store.connect()
        indexed = rag_store.index_stats(conn)["chunks"]
        conn.close()
        if indexed:
            print(f"[RAG] 索引 {indexed} 条，{await run_in_threadpool(rag_retriever.warmup)}")
        else:
            print("[RAG] 索引为空，跳过预热（先执行 python -m rag.indexer）")
    except Exception as e:  # noqa: BLE001
        print(f"[RAG] 预热跳过：{type(e).__name__}: {e}")

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
app.include_router(agent.router, prefix="/api/v1/agent", tags=["诊断Agent"])
app.include_router(review.router, prefix="/api/v1/review", tags=["数据飞轮"])

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


@app.get("/health/model")
async def model_health():
    """推理模型状态探针：ready=false 时 detail 会给出失败原因"""
    info = model_service.describe()
    return {
        "status": "ok" if info["ready"] else "unavailable",
        "detail": info,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)