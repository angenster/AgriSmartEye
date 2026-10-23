"""
智农慧眼 - 类别标签定义（单一事实来源）

本模块刻意不引入任何第三方依赖，供三处共享：
  - ai-model/utils/dataset.py   训练时的标签映射
  - ai-model/inference/         推理时的 id → 类别名 还原
  - backend/                    落库、复核队列下拉、报告生成

标签顺序即为模型输出向量的下标顺序，任何改动都会使已训练的权重失效，
必须同时升版本号并重训。

--------------------------------------------------------------------------
v1.1（2026-10-20）：标签空间从 42 类收缩到 12 类。

原因见 docs/datasets.md：公开数据集对原 42 类的精确覆盖率仅 21%，
且多用症状名而非病原名。v1 只保留「有公开数据、且语义可对应」的类别。

**许可状态（2026-10-20 更新）**：芒果类数据改用 Kaggle 上的 VN-MangoLeaf
（CC BY 4.0），而非原先的 MangoLeafBD（CC BY-NC 3.0）。
因此 v1 使用的全部数据均可商用。若后续回退到 MangoLeafBD，
该版本将受 NC 限制，不得用于商业用途。

完整的 42 类保留在 KNOWLEDGE_CLASSES 中，供 RAG 知识库与文档引用；
模型不再输出这些类别。
--------------------------------------------------------------------------
"""

# 数据集版本：标签体系变更时必须递增，并与 model_versions.version_tag 对齐
LABELS_VERSION = "v1.1-research"

# 作物种类映射（6 类，顺序即模型 crop 头输出维度）
# 仅包含 v1 训练数据中实际出现的作物；自采补盲后可再扩展。
CROP_CLASSES = [
    "芒果", "香蕉", "菠萝", "火龙果", "木瓜", "咖啡",
]

# 病虫害种类映射（12 类，顺序即模型 disease 头输出维度）
DISEASE_CLASSES = [
    # 芒果 (2) —— 来源 VN-MangoLeaf (Kaggle)，CC BY 4.0，可商用
    "芒果炭疽病", "芒果白粉病",
    # 香蕉 (3)
    "香蕉枯萎病", "香蕉黑星病", "香蕉叶斑病",
    # 菠萝 (2)
    "菠萝心腐病", "菠萝粉蚧",
    # 火龙果 (1)
    "火龙果溃疡病",
    # 木瓜 (2)
    "木瓜炭疽病", "木瓜花叶病",
    # 咖啡 (1)
    "咖啡锈病",
    # 无病虫害
    "健康",
]

# 严重程度（3 级）。
# 注意：公开数据集没有严重度标注（唯一例外是咖啡锈病分割集），
# 因此 v1 **不训练 severity 头**，推理时该头输出不可信。
SEVERITY_CLASSES = ["轻度", "中度", "重度"]
SEVERITY_TRAINED = False

# 无需施药的类别：Agent 与报告生成据此跳过用药建议
HEALTHY_LABEL = "健康"

# 复核队列中用于标记「12 类之外」的保留标签
UNKNOWN_LABEL = "其他/未知"

# 完整的历史 42 类标签空间。模型不再输出，但 RAG 语料、文档与
# 复核队列的"历史数据"仍会引用它。不要删除——删除会让旧记录失去可读性。
KNOWLEDGE_CLASSES = [
    # 芒果 (6)
    "芒果炭疽病", "芒果白粉病", "芒果细菌性角斑病", "芒果介壳虫", "芒果蓟马", "芒果瘿螨",
    # 荔枝 (5)
    "荔枝霜疫霉病", "荔枝炭疽病", "荔枝蝽", "荔枝蒂蛀虫", "荔枝瘿螨",
    # 槟榔 (5)
    "槟榔黄化病", "槟榔炭疽病", "槟榔细菌性条斑病", "槟榔红脉穗螟", "槟榔蚧壳虫",
    # 香蕉 (5)
    "香蕉枯萎病", "香蕉叶斑病", "香蕉黑星病", "香蕉象甲", "香蕉蚜虫",
    # 菠萝 (4)
    "菠萝心腐病", "菠萝黑腐病", "菠萝粉蚧", "菠萝红蜘蛛",
    # 火龙果 (4)
    "火龙果溃疡病", "火龙果炭疽病", "火龙果蜗牛", "火龙果介壳虫",
    # 木瓜 (4)
    "木瓜花叶病", "木瓜炭疽病", "木瓜红蜘蛛", "木瓜介壳虫",
    # 其他 (9)
    "椰子红环腐病", "橡胶白粉病", "胡椒瘟病", "咖啡锈病",
    "茶叶茶饼病", "甘蔗赤腐病", "木薯细菌性枯萎病", "剑麻斑马纹病",
    "健康",
]

# 数量自检：与模型输出的三个头维度一一对应，防止标签表被误改后静默错位
assert len(CROP_CLASSES) == 6, f"CROP_CLASSES 应为 6 类，实际 {len(CROP_CLASSES)}"
assert len(DISEASE_CLASSES) == 12, f"DISEASE_CLASSES 应为 12 类，实际 {len(DISEASE_CLASSES)}"
assert len(SEVERITY_CLASSES) == 3, f"SEVERITY_CLASSES 应为 3 级，实际 {len(SEVERITY_CLASSES)}"
assert len(KNOWLEDGE_CLASSES) == 42, f"KNOWLEDGE_CLASSES 应为 42 类，实际 {len(KNOWLEDGE_CLASSES)}"
assert set(DISEASE_CLASSES).issubset(set(KNOWLEDGE_CLASSES)), "v1 标签必须都来自 42 类知识空间"


def crop_name(idx: int) -> str:
    """作物 id → 名称；越界返回占位符而不抛错，避免单张异常图打断整批推理"""
    return CROP_CLASSES[idx] if 0 <= idx < len(CROP_CLASSES) else f"未知作物({idx})"


def disease_name(idx: int) -> str:
    """病虫害 id → 名称；越界返回占位符"""
    return DISEASE_CLASSES[idx] if 0 <= idx < len(DISEASE_CLASSES) else f"未知病害({idx})"


def severity_name(idx: int) -> str:
    """严重程度 id → 名称；越界返回占位符"""
    return SEVERITY_CLASSES[idx] if 0 <= idx < len(SEVERITY_CLASSES) else f"未知程度({idx})"


def is_healthy(disease_label: str) -> bool:
    """判断病虫害标签是否为健康"""
    return disease_label == HEALTHY_LABEL


def is_model_label(disease_label: str) -> bool:
    """判断标签是否属于 v1 模型能够输出的类别"""
    return disease_label in DISEASE_CLASSES


def crop_of_label(disease_label: str) -> str | None:
    """从病害标签里解析出作物前缀。

    DISEASE_CLASSES 的命名是"作物+病害"（如 芒果细菌性角斑病），
    因此可以反推出所属作物；"健康" 这类无前缀的返回 None。
    用于跨分类头的一致性检查：crop 头与 disease 头的作物对不上时，
    说明两个头互相矛盾，结果不可信。
    """
    if not disease_label or disease_label == HEALTHY_LABEL:
        return None
    for crop in sorted(CROP_CLASSES, key=len, reverse=True):
        if disease_label.startswith(crop):
            return crop
    return None
