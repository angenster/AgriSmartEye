"""
RAG 存储层 —— 索引表 DDL 与连接管理。

单独用裸 sqlite3 连接而不是复用 ORM 的 session，原因有二：
  1. sqlite-vec 是 loadable extension，必须逐连接加载；
     挂在全局 ORM 引擎上会让每个业务连接都背上这个开销。
  2. 建索引与向量检索都是批量操作，不需要 ORM 的对象映射。

中文分词：FTS5 内置的 unicode61/trigram 对中文基本不可用
（实测 unicode61 下 "炭疽病" 命中 0 条），因此额外存一份 jieba 切分后的
title_seg / text_seg 供 FTS5 索引，原文字段 text 只用于展示与引用摘录。
"""
import os
import sqlite3
from pathlib import Path
from typing import Optional

# bge-small-zh-v1.5 的输出维度
EMBEDDING_DIM = 512


def db_path() -> str:
    """从 DATABASE_URL 解析出 SQLite 文件路径。

    非 SQLite（如 PostgreSQL）时，RAG 需要另行迁移存储，这里直接报错而不是静默降级。
    """
    url = os.getenv("DATABASE_URL", "sqlite:///./zhinong.db")
    if not url.startswith("sqlite"):
        raise RuntimeError(
            f"RAG 目前只实现了 SQLite 后端（sqlite-vec），当前 DATABASE_URL={url!r}。"
        )
    path = url.split("sqlite:///", 1)[-1]
    return path


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    """打开一个已加载 sqlite-vec 扩展的连接。"""
    import sqlite_vec

    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"加载 sqlite-vec 扩展失败（{type(e).__name__}: {e}）。"
            "Windows 上需要 Python 的 sqlite3 支持 enable_load_extension。"
        ) from e

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _vec_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT vec_version()")
        return True
    except sqlite3.OperationalError:
        return False


def ensure_schema(conn: sqlite3.Connection) -> None:
    """建索引相关表（幂等）。"""
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            source        TEXT NOT NULL,      -- 来源标识，可溯源（红线：宁少勿滥）
            ref_id        TEXT,               -- 来源内的标识，如 pest_info.id
            title         TEXT NOT NULL,
            text          TEXT NOT NULL,      -- 原文，用于展示与引用摘录
            title_seg     TEXT NOT NULL,      -- jieba 切分后，仅供 FTS5 索引
            text_seg      TEXT NOT NULL,      -- jieba 切分后，仅供 FTS5 索引
            metadata_json TEXT,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # FTS5 普通表（非 external content）：rowid 与 knowledge_chunks.id 对齐，
    # 查询后按 rowid join 回源表。省掉 trigger 同步带来的失败面。
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts "
        "USING fts5(title_seg, text_seg, tokenize='unicode61')"
    )

    # 逐行向量表；rowid 与 knowledge_chunks.id 对齐
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS chunk_embeddings "
        f"USING vec0(embedding float[{EMBEDDING_DIM}])"
    )
    conn.commit()


def reset_index(conn: sqlite3.Connection) -> None:
    """清空索引（重建前调用）"""
    conn.execute("DELETE FROM knowledge_chunks")
    conn.execute("DELETE FROM knowledge_fts")
    conn.execute("DELETE FROM chunk_embeddings")
    conn.commit()


def index_stats(conn: sqlite3.Connection) -> dict:
    chunks = conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0]
    try:
        vecs = conn.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()[0]
    except sqlite3.OperationalError:
        vecs = 0
    sources = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT source, COUNT(*) FROM knowledge_chunks GROUP BY source"
        ).fetchall()
    }
    return {
        "chunks": chunks,
        "embeddings": vecs,
        "sources": sources,
        "vec_available": _vec_available(conn),
        "embedding_dim": EMBEDDING_DIM,
    }
