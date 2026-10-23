"""
推理服务 —— 在 FastAPI 进程内以单例持有 InferenceEngine。

设计要点：
  - 权重路径 / 后端 / 设备均可由环境变量覆盖（见下面 _env_* 常量）。
  - 未配置权重时默认以 DEMO 模式启动（ImageNet 骨干 + 随机分类头），
    并通过 is_demo / model_version 一路透传到 API 响应，避免"以为在用真模型"。
  - torch 缺失或权重损坏时不阻塞进程启动：推理接口返回 503，
    其余路由（认证、田块、知识库）照常可用。
  - 加载耗时数秒，放在 lifespan 里一次性完成，并对首帧做 warmup，
    使首个请求不必承担冷启动开销。
"""
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

# 让 backend 能 import ai-model 下的 labels / models / inference
AI_MODEL_DIR = Path(__file__).resolve().parents[2] / "ai-model"
if str(AI_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(AI_MODEL_DIR))

# 默认权重位置与 .gitignore 中忽略的目录一致
DEFAULT_WEIGHTS = AI_MODEL_DIR / "checkpoints" / "best.pt"

DEMO_MODEL_VERSION = "demo-untrained"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class ModelNotAvailable(RuntimeError):
    """模型未就绪（torch 缺失 / 权重损坏 / demo 未获授权）"""


class ModelService:
    """单例推理服务。全进程共用一份模型，避免每次请求重复加载。"""

    def __init__(self) -> None:
        self.weights_path = os.getenv("MODEL_WEIGHTS_PATH", str(DEFAULT_WEIGHTS))
        self.backend = os.getenv("MODEL_BACKEND", "pytorch")
        self.device = os.getenv("MODEL_DEVICE", "auto")
        # 缺省允许 demo，否则仓库里没有权重时后端根本起不来；
        # 生产部署应显式设为 false，让缺权重直接失败而不是静默降级。
        self.allow_demo = _env_bool("ALLOW_DEMO_MODEL", True)

        self._engine: Optional[Any] = None
        self._load_error: Optional[str] = None
        self._lock = threading.Lock()

    # ---------- 生命周期 ----------

    def load(self) -> None:
        """加载模型并 warmup。失败时记录原因而不抛错，由接口层转成 503。"""
        with self._lock:
            if self._engine is not None or self._load_error is not None:
                return
            try:
                from inference.inference import InferenceEngine

                engine = InferenceEngine(
                    model_path=self.weights_path,
                    backend=self.backend,
                    device=self.device,
                    allow_demo=self.allow_demo,
                )
                # warmup：首帧因惰性初始化会明显偏慢，提前吃掉
                engine.predict(Image.new("RGB", (224, 224), (128, 128, 128)))
                self._engine = engine
            except Exception as exc:  # noqa: BLE001 - 需把任意加载失败转成可读状态
                self._load_error = f"{type(exc).__name__}: {exc}"
                print(f"[ERROR] 推理模型加载失败: {self._load_error}")

    def warmup_done(self) -> bool:
        return self._engine is not None

    # ---------- 状态 ----------

    @property
    def is_ready(self) -> bool:
        return self._engine is not None

    @property
    def is_demo(self) -> bool:
        return bool(self._engine is not None and getattr(self._engine, "is_demo", False))

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    @property
    def model_version(self) -> str:
        """写入 DetectionRecord.model_version，供飞轮的版本追溯使用。"""
        if self.is_demo:
            return DEMO_MODEL_VERSION
        if self._engine is not None and getattr(self._engine, "version", None):
            return self._engine.version
        return Path(self.weights_path).stem or "unknown"

    @property
    def labels_version(self) -> str:
        from labels import LABELS_VERSION

        return LABELS_VERSION

    def describe(self) -> Dict:
        """供 /health 之类的探针展示模型状态"""
        return {
            "ready": self.is_ready,
            "is_demo": self.is_demo,
            "model_version": self.model_version,
            "labels_version": self.labels_version,
            "backend": self.backend,
            "device": self.device,
            "weights_path": self.weights_path,
            "load_error": self._load_error,
        }

    # ---------- 推理 ----------

    def predict(self, image) -> Dict:
        """跑一次推理。未就绪时抛 ModelNotAvailable，由路由层转 503。"""
        if self._engine is None:
            raise ModelNotAvailable(self._load_error or "推理模型尚未加载")
        return self._engine.predict(image)


# 模块级单例：main.py 在 lifespan 中调用 load()
model_service = ModelService()
