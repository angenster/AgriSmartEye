"""
嵌入模型封装 —— bge-small-zh-v1.5，本地 CPU 推理，进程内单例。

两个环境相关的坑：
  1. HF_ENDPOINT 必须在 import huggingface_hub 之前设置。hub 在导入时就把端点
     读进模块常量，之后再改 os.environ 不生效。国内直连 huggingface.co 的
     模型 CDN 通常不通，需走 hf-mirror.com 镜像。
  2. 模型加载耗时数十秒且占内存，必须单例 + 懒加载，不能每次检索都建一次。
"""
import os
import threading
from typing import List, Optional

# 默认走镜像；如需直连可显式设 HF_ENDPOINT=https://huggingface.co
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"
DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"

_lock = threading.Lock()
_model = None
_load_error: Optional[str] = None


class EmbedderUnavailable(RuntimeError):
    """嵌入模型不可用（未下载 / 网络不通 / 依赖缺失）"""


def _ensure_endpoint() -> None:
    """在 huggingface_hub 被导入前设置镜像端点"""
    if "HF_ENDPOINT" not in os.environ and os.getenv("RAG_USE_HF_MIRROR", "true").lower() in (
        "1", "true", "yes", "on"
    ):
        os.environ["HF_ENDPOINT"] = DEFAULT_HF_ENDPOINT


def model_name() -> str:
    return os.getenv("RAG_EMBED_MODEL", DEFAULT_MODEL)


def load_embedder():
    """懒加载单例。失败时抛 EmbedderUnavailable（只尝试一次，避免反复卡网络）。"""
    global _model, _load_error

    if _model is not None:
        return _model
    if _load_error is not None:
        raise EmbedderUnavailable(_load_error)

    with _lock:
        if _model is not None:
            return _model
        if _load_error is not None:
            raise EmbedderUnavailable(_load_error)

        _ensure_endpoint()
        try:
            from sentence_transformers import SentenceTransformer

            name = model_name()
            print(f"[RAG] 正在加载嵌入模型 {name} ...")
            _model = SentenceTransformer(name)
            print(f"[RAG] 嵌入模型就绪，维度 {_model.get_sentence_embedding_dimension()}")
        except Exception as e:  # noqa: BLE001
            _load_error = (
                f"加载嵌入模型失败：{type(e).__name__}: {e}。"
                f"当前 HF_ENDPOINT={os.environ.get('HF_ENDPOINT')}，"
                "国内环境通常需要 hf-mirror.com 镜像。"
            )
            raise EmbedderUnavailable(_load_error) from e

    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """批量编码，返回归一化后的向量（点积即余弦相似度）"""
    model = load_embedder()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [list(map(float, v)) for v in vectors]


def embed_query(query: str) -> List[float]:
    """bge 系列检索时建议给查询加指令前缀，可小幅提升召回"""
    return embed_texts([f"为这个句子生成表示以用于检索相关文章：{query}"])[0]


def is_ready() -> bool:
    return _model is not None


def load_error() -> Optional[str]:
    return _load_error
