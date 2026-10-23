"""
agent 包 —— 诊断 Agent：工具层 / planner / ReAct 循环 / 报告组装

这里显式把 ai-model 目录加入 sys.path（labels.py / models / inference 都在那里）。
放在包初始化处而不是"某个模块恰好先被导入时顺手设置"，否则导入顺序一变就会崩。
"""
import sys
from pathlib import Path

AI_MODEL_DIR = Path(__file__).resolve().parents[2] / "ai-model"
if str(AI_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(AI_MODEL_DIR))
