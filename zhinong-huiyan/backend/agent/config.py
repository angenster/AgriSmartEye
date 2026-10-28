"""
Agent 配置 —— 阈值、预算与外部模型接入参数，全部可由环境变量覆盖。

密钥一律走环境变量，不写入仓库、不下发前端（项目红线 #4）。
"""
import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """读取 backend/.env.local（已在 .gitignore 中），只填充尚未设置的变量。

    密钥仍然只通过环境变量使用，这个文件只是本机启动时的一个便捷入口；
    进程环境里已有的值优先，不会被文件覆盖。
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


_load_env_file(Path(__file__).resolve().parents[1] / ".env.local")

# ---------- 双引擎仲裁阈值（方案 §5.4）----------
# 代码层强制，不依赖 Agent 自觉
TAU_HIGH = float(os.getenv("AGENT_TAU_HIGH", "0.85"))   # 高于此值且 top1-top2 间距足够 → 直接采纳 CNN
TAU_LOW = float(os.getenv("AGENT_TAU_LOW", "0.60"))     # 低于此值 → 强制升级 VLM
MARGIN = float(os.getenv("AGENT_MARGIN", "0.15"))       # top1-top2 最小间距

# ---------- 步数预算 ----------
MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "12"))

# ---------- 用药安全（红线 #3）----------
# 这些作物的低置信结果必须转人工，不允许 Agent 自行拍板
HIGH_VALUE_CROPS = {"槟榔", "芒果"}

# ---------- VLM 接入（OpenAI 兼容 vision 接口）----------
VLM_API_KEY = os.getenv("VLM_API_KEY")
VLM_BASE_URL = os.getenv("VLM_BASE_URL", "https://api.openai.com/v1")
VLM_MODEL = os.getenv("VLM_MODEL", "gpt-4o-mini")
VLM_TIMEOUT_S = float(os.getenv("VLM_TIMEOUT_S", "60"))

# ---------- LLM planner 接入（OpenAI 兼容 function calling）----------
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "60"))


def vlm_configured() -> bool:
    return bool(VLM_API_KEY)


def llm_configured() -> bool:
    return bool(LLM_API_KEY)
