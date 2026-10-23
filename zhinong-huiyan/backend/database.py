"""
数据库配置与连接管理
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./zhinong.db"  # 默认使用SQLite，无需安装PostgreSQL
)

# SQLite配置
if "sqlite" in DATABASE_URL:
    # 不用 StaticPool：它让全应用共用同一条连接，而诊断 Agent 一次运行会持有
    # session 数秒（含推理与外部模型调用），并发请求会互相阻塞甚至串到别人的事务上。
    # NullPool 让每个 session 各拿一条连接，配合下面的 WAL 与 busy_timeout 处理争用。
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")      # 读写不互相阻塞
        cursor.execute("PRAGMA busy_timeout=30000")    # 写锁等待上限 30s
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """数据库会话依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DBContext:
    """数据库上下文管理器"""
    def __init__(self):
        self.db: Session = SessionLocal()

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.db.rollback()
        else:
            self.db.commit()
        self.db.close()