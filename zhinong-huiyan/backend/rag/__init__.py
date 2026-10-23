"""
rag 包 —— 农技知识检索：种子语料 / 索引管道 / 混合检索

检索结果携带来源标识（source），供诊断报告生成可核对的结构化引用。
"""
import sys
from pathlib import Path

# ai-model 目录（labels.py 所在）加入 sys.path。
# 与 agent 包同样的处理：显式设置，不依赖"某个模块恰好先被导入"。
AI_MODEL_DIR = Path(__file__).resolve().parents[2] / "ai-model"
if str(AI_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(AI_MODEL_DIR))
