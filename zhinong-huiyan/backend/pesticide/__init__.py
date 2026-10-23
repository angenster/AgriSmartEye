"""农药登记数据（query_pesticide 的数据源）。"""
import sys
from pathlib import Path

# labels.py 在 ai-model 下；与 agent/、rag/ 保持同样的路径注入方式
AI_MODEL_DIR = Path(__file__).resolve().parents[2] / "ai-model"
if str(AI_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(AI_MODEL_DIR))
