"""
索引管道 —— 把语料切块、嵌入，双写进 knowledge_chunks + knowledge_fts + chunk_embeddings。

用法：
    python -m rag.indexer                # 用种子语料重建索引
    python -m rag.indexer --with-pest-info   # 同时索引 pest_info 表里的条目
"""
import argparse
import json
import sqlite3
from typing import Dict, List, Optional

import jieba

from rag import seed_corpus, store
from rag.embedder import EmbedderUnavailable, embed_texts


def segment(text: str) -> str:
    """中文分词。FTS5 的 unicode61 不认识中文词边界，必须先切分再入索引。"""
    return " ".join(t for t in jieba.lcut(text or "") if t.strip())


def _pest_info_chunks(conn: sqlite3.Connection) -> List[Dict]:
    """把 pest_info 表里的条目也纳入索引（该项目本就有这张表作为知识容器）"""
    try:
        rows = conn.execute(
            "SELECT id, name, crop_type, category, symptoms, causes, prevention, treatment FROM pest_info"
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    chunks = []
    for r in rows:
        parts = []
        if r["symptoms"]:
            parts.append(f"症状：{r['symptoms']}")
        if r["causes"]:
            parts.append(f"成因：{r['causes']}")
        for label, field in (("预防", r["prevention"]), ("防治", r["treatment"])):
            if field:
                try:
                    items = json.loads(field) if isinstance(field, str) else field
                    parts.append(f"{label}：{'；'.join(items)}")
                except (json.JSONDecodeError, TypeError):
                    parts.append(f"{label}：{field}")
        chunks.append({
            "source": "pest_info",
            "ref_id": str(r["id"]),
            "title": f"{r['crop_type'] or ''}·{r['name'] or ''}".strip("·"),
            "text": "\n".join(parts),
            "metadata": {"name": r["name"], "crop": r["crop_type"],
                         "category": r["category"], "reviewed": True},
        })
    return chunks


def build_index(
    chunks: Optional[List[Dict]] = None,
    reset: bool = True,
    with_pest_info: bool = False,
    path: Optional[str] = None,
) -> Dict:
    """建索引。返回统计信息。

    嵌入模型不可用时**不静默降级**：直接报错，让调用方明确知道
    当前只有关键词索引可用，而不是以为向量检索也在工作。
    """
    conn = store.connect(path)
    store.ensure_schema(conn)

    if chunks is None:
        chunks = seed_corpus.to_chunks()
    if with_pest_info:
        chunks = chunks + _pest_info_chunks(conn)

    if reset:
        store.reset_index(conn)

    if not chunks:
        return {"indexed": 0, "note": "没有可索引的内容"}

    titles = [c["title"] for c in chunks]
    texts = [c["text"] for c in chunks]

    # 嵌入失败就整体失败，避免产出一个"看起来建好了但只能用一半"的索引
    vectors = embed_texts(texts)

    import sqlite_vec

    for chunk, vec in zip(chunks, vectors):
        cur = conn.execute(
            "INSERT INTO knowledge_chunks (source, ref_id, title, text, title_seg, text_seg, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                chunk["source"],
                chunk.get("ref_id"),
                chunk["title"],
                chunk["text"],
                segment(chunk["title"]),
                segment(chunk["text"]),
                json.dumps(chunk.get("metadata") or {}, ensure_ascii=False),
            ),
        )
        cid = cur.lastrowid
        conn.execute(
            "INSERT INTO knowledge_fts (rowid, title_seg, text_seg) VALUES (?, ?, ?)",
            (cid, segment(chunk["title"]), segment(chunk["text"])),
        )
        conn.execute(
            "INSERT INTO chunk_embeddings (rowid, embedding) VALUES (?, ?)",
            (cid, sqlite_vec.serialize_float32(vec)),
        )

    conn.commit()
    stats = store.index_stats(conn)
    conn.close()
    return {"indexed": len(chunks), **stats}


def main() -> None:
    parser = argparse.ArgumentParser(description="构建农技知识检索索引")
    parser.add_argument("--with-pest-info", action="store_true", help="同时索引 pest_info 表")
    parser.add_argument("--no-reset", action="store_true", help="追加而非重建")
    args = parser.parse_args()

    stats = build_index(reset=not args.no_reset, with_pest_info=args.with_pest_info)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
