"""
混合检索 —— FTS5 关键词 + sqlite-vec 向量 → RRF 融合 → 可选重排。

    query → ├─ FTS5 (bm25)        → top candidate_k
            └─ 向量 (cosine)       → top candidate_k
         → RRF 融合 (k=60) → top10
         → bge-reranker 重排 → top_k     （RAG_RERANK=bge 时启用）
         → 返回 [{chunk_id, title, text, score, source, ...}]

降级策略（都不静默）：
  - 嵌入模型不可用 → 退化为纯 FTS 检索，并在返回值里标 vector_ok=false 说明原因
  - 重排模型不可用 → 退化为 RRF 顺序，标 rerank_ok=false
"""
import json
import os
import sqlite3
from typing import Dict, List, Optional

import jieba

from rag import store

RRF_K = 60

_reranker = None
_rerank_error: Optional[str] = None
_rerank_lock = None


# ---------------------------------------------------------------- 单路召回

def _fts_search(conn: sqlite3.Connection, query: str, limit: int) -> List[Dict]:
    """FTS5 bm25 关键词召回。查询词同样要先分词。"""
    tokens = [t for t in jieba.lcut(query or "") if t.strip() and not t.isspace()]
    tokens = [t for t in tokens if t not in ("，", "。", "、", "；", "：", "（", "）", "的", "了")]
    if not tokens:
        return []

    # 每个词加引号做短语匹配，避免 FTS5 把标点当语法
    match_expr = " OR ".join(f'"{t}"' for t in tokens)
    try:
        rows = conn.execute(
            "SELECT rowid, bm25(knowledge_fts) AS score FROM knowledge_fts "
            "WHERE knowledge_fts MATCH ? ORDER BY score LIMIT ?",
            (match_expr, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    # bm25 越小越相关，转成"越大越好"的分数以便与向量分数统一看待
    return [{"rowid": r["rowid"], "score": -float(r["score"]), "rank": i + 1}
            for i, r in enumerate(rows)]


def _vector_search(conn: sqlite3.Connection, query: str, limit: int) -> List[Dict]:
    """sqlite-vec 向量召回。嵌入不可用时抛 EmbedderUnavailable 由上层捕获。"""
    import sqlite_vec
    from rag.embedder import embed_query

    vec = embed_query(query)
    rows = conn.execute(
        "SELECT rowid, distance FROM chunk_embeddings WHERE embedding MATCH ? "
        "ORDER BY distance LIMIT ?",
        (sqlite_vec.serialize_float32(vec), limit),
    ).fetchall()
    return [{"rowid": r["rowid"], "score": 1.0 - float(r["distance"]), "rank": i + 1}
            for i, r in enumerate(rows)]


# ---------------------------------------------------------------- 融合与重排

def _rrf_fuse(rankings: List[List[Dict]], k: int = RRF_K) -> Dict[int, float]:
    """Reciprocal Rank Fusion：只用名次，不用原始分数，天然免去量纲归一化。"""
    fused: Dict[int, float] = {}
    for ranking in rankings:
        for item in ranking:
            fused[item["rowid"]] = fused.get(item["rowid"], 0.0) + 1.0 / (k + item["rank"])
    return fused


def _get_reranker():
    """懒加载重排模型。失败只记录原因，不影响主流程。"""
    global _reranker, _rerank_error, _rerank_lock
    import threading

    if _rerank_lock is None:
        _rerank_lock = threading.Lock()

    if _reranker is not None:
        return _reranker
    if _rerank_error is not None:
        return None

    with _rerank_lock:
        if _reranker is not None:
            return _reranker
        if _rerank_error is not None:
            return None
        try:
            from rag.embedder import _ensure_endpoint
            _ensure_endpoint()
            from sentence_transformers import CrossEncoder

            name = os.getenv("RAG_RERANK_MODEL", "BAAI/bge-reranker-base")
            print(f"[RAG] 正在加载重排模型 {name} ...")
            _reranker = CrossEncoder(name)
            print("[RAG] 重排模型就绪")
        except Exception as e:  # noqa: BLE001
            _rerank_error = f"{type(e).__name__}: {e}"
            print(f"[RAG] 重排模型不可用，退化为 RRF 顺序: {_rerank_error}")
    return _reranker


def _rerank_on() -> bool:
    """默认 auto：模型可用就开。

    评测（python -m rag.eval_retrieval）显示开启重排后 top-1 由 75% 升至 83.3%、
    Recall@5 由 83.3% 升至 100%，主要集中在症状描述类查询上——而这正是农户的
    真实输入形式。精确病名查询原本会被重排拉低，已由 _pin_exact_matches 兜住。
    """
    mode = os.getenv("RAG_RERANK", "auto").strip().lower()
    if mode in ("1", "true", "yes", "on", "bge"):
        return True
    if mode == "auto":
        return _get_reranker() is not None
    return False


def warmup() -> Dict:
    """预加载重排模型。放在应用启动阶段调用，避免首个检索请求承担约 20s 冷启动。"""
    if os.getenv("RAG_RERANK", "auto").strip().lower() == "off":
        return {"rerank": False, "reason": "RAG_RERANK=off"}
    reranker = _get_reranker()
    return {"rerank": reranker is not None, "error": _rerank_error}


# ---------------------------------------------------------------- 对外接口

def _exact_label_match_ids(conn: sqlite3.Connection, query: str) -> List[int]:
    """查询中若出现已知病虫害全名，返回完全匹配的 chunk id（长名优先）。

    为什么需要这一步：评测显示交叉编码器重排会把「芒果炭疽病」这类精确病名
    查询从第 1 名挤到第 5 名 —— 因为它分不清「芒果/槟榔/荔枝炭疽病」这种
    只差一个词的文本。而 Agent 调用 search_knowledge 时传的恰恰是预测出的
    精确病名，正好踩在这个弱点上。
    精确全名匹配是比任何模型分数都强的确定信号，因此单独兜底。
    """
    from labels import KNOWLEDGE_CLASSES

    matched: List[int] = []
    # 用 42 类知识空间而不是模型的 12 类输出空间：
    # 检索服务于人工搜索与 Agent 查证，覆盖面应大于模型能力。
    for name in sorted(KNOWLEDGE_CLASSES, key=len, reverse=True):
        if name and name in query:
            row = conn.execute(
                "SELECT id FROM knowledge_chunks WHERE ref_id = ? LIMIT 1", (name,)
            ).fetchone()
            if row and row["id"] not in matched:
                matched.append(row["id"])
    return matched


def _pin_exact_matches(candidates: List, conn: sqlite3.Connection, query: str) -> List:
    """把精确命中已知病名的 chunk 提到最前，其余保持原序。"""
    pinned = _exact_label_match_ids(conn, query)
    if not pinned:
        return candidates
    order = {cid: i for i, cid in enumerate(pinned)}
    indexed = list(enumerate(candidates))
    indexed.sort(key=lambda pair: (order.get(pair[1][0], len(order)), pair[0]))
    return [c for _, c in indexed]


def search(query: str, top_k: int = 5, candidate_k: int = 20,
           path: Optional[str] = None) -> Dict:
    """混合检索。返回 dict，包含 chunks 与本次检索的实际工作模式。"""
    conn = store.connect(path)
    try:
        store.ensure_schema(conn)

        fts_hits = _fts_search(conn, query, candidate_k)

        embedder_error = None
        vec_hits: List[Dict] = []
        try:
            vec_hits = _vector_search(conn, query, candidate_k)
        except Exception as e:  # noqa: BLE001 - 嵌入不可用是预期内的降级路径
            embedder_error = f"{type(e).__name__}: {e}"

        rankings = [r for r in (fts_hits, vec_hits) if r]
        if not rankings:
            return {"chunks": [], "mode": "none", "vector_ok": False,
                    "fts_hits": 0, "vector_hits": 0, "note": "关键词与向量均无命中"}

        fused = _rrf_fuse(rankings)
        ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)

        ids = [cid for cid, _ in ordered]
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT id, source, ref_id, title, text, metadata_json "
            f"FROM knowledge_chunks WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
        by_id = {r["id"]: r for r in rows}
        candidates = [(cid, score, by_id[cid]) for cid, score in ordered if cid in by_id]

        rerank_ok = False
        mode = "hybrid_rrf"
        if _rerank_on():
            reranker = _get_reranker()
            if reranker is not None and candidates:
                pairs = [(query, c[2]["text"]) for c in candidates]
                scores = reranker.predict(pairs)
                candidates = [c for _, c in sorted(
                    zip(scores, candidates), key=lambda x: -float(x[0])
                )]
                rerank_ok = True
                mode = "hybrid_rerank"

        # 精确病名兜底：Agent 传进来的往往就是预测出的病名全称，
        # 这一步保证它不会被重排模型挤下去
        candidates = _pin_exact_matches(candidates, conn, query)

        chunks = []
        for cid, score, row in candidates[:top_k]:
            meta = {}
            if row["metadata_json"]:
                try:
                    meta = json.loads(row["metadata_json"])
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            chunks.append({
                "chunk_id": cid,
                "title": row["title"],
                "text": row["text"],
                "score": round(float(score), 6),
                "source": row["source"],
                "ref_id": row["ref_id"],
                "reviewed": meta.get("reviewed"),
            })

        return {
            "chunks": chunks,
            "mode": mode if vec_hits else "fts_only",
            "vector_ok": bool(vec_hits),
            "rerank_ok": rerank_ok,
            "fts_hits": len(fts_hits),
            "vector_hits": len(vec_hits),
            "embedder_error": embedder_error,
        }
    finally:
        conn.close()


def stats(path: Optional[str] = None) -> Dict:
    conn = store.connect(path)
    try:
        store.ensure_schema(conn)
        return store.index_stats(conn)
    finally:
        conn.close()
