"""
公开数据集登记表 —— 单一事实来源。

这里记录每个数据集的**已核实**元信息（类别、数量、许可、获取方式）以及
它与本项目 `ai-model/labels.py` 标签空间的映射关系。

维护规则：
  1. 只有亲自打开过原始页面并抄下类别的条目，verified 才能写 True。
  2. license 与 commercial_ok 必须分开记录：CC BY-NC 允许研究但禁止商用，
     而本项目 README 的商业模式是硬件销售 + SaaS 订阅，两者冲突。
  3. 映射分 exact / approx 两级。approx 表示类别语义接近但不是同一对象
     （例如 Gall Midge 与 瘿螨、Bacterial Canker 与 细菌性角斑病），
     默认不进入训练集，需显式 --include-approx。
  4. 没有映射的类别（mapping 中不出现）一律丢弃并计入浪费率。

数据来源页面见 url；抓取日期见 verified_at。
"""
from typing import Dict, List, Optional, Tuple

# 映射值：(本项目标签, "exact" | "approx")
Mapping = Dict[str, Tuple[str, str]]

DATASETS: List[dict] = [
    # ------------------------------------------------------------------ 芒果
    {
        "key": "mango_xdom",
        "name": "Mango Leaf Disease (Bangladesh)",
        "crop": "芒果",
        "url": "https://www.kaggle.com/datasets/mdsaymonahammad/mango-leaf-disease",
        "license": "CC BY-SA 4.0（上游疑为 MangoLeafBD，CC BY-NC）",
        "commercial_ok": False,
        "eval_only": True,
        "images": 2485,
        "classes": [
            "Anthracnose", "Bacterial Canker", "Cutting Weevil", "Die Back",
            "Gall Midge", "Healthy Leaf", "Powdery Mildew", "Sooty Mould",
        ],
        "mapping": {
            "Anthracnose": ("芒果炭疽病", "exact"),
            "Powdery Mildew": ("芒果白粉病", "exact"),
            "Healthy Leaf": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Kaggle 公开下载端点",
        "notes": "类别表与 MangoLeafBD 完全一致，几乎可确定是其转载。"
                 "**仅用于跨域评测，不参与训练**（eval_only）。",
    },
    # ------------------------------------------------------------------ 芒果（Mendeley，已弃用）
    {
        "key": "mango_leaf_bd",
        "name": "MangoLeafBD",
        "crop": "芒果",
        "url": "https://data.mendeley.com/datasets/hxsnvwty3r/1",
        "license": "CC BY-NC 3.0",
        "commercial_ok": False,          # NC：禁止商业使用
        "images": 4000,
        "classes": [
            "Anthracnose", "Bacterial Canker", "Cutting Weevil",
            "Die Back", "Gall Midge", "Powdery Mildew", "Sooty Mould", "Healthy",
        ],
        "mapping": {
            "Anthracnose": ("芒果炭疽病", "exact"),
            "Powdery Mildew": ("芒果白粉病", "exact"),
            "Bacterial Canker": ("芒果细菌性角斑病", "approx"),
            "Gall Midge": ("芒果瘿螨", "approx"),
            "Healthy": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Mendeley 'Download All'，无需账号",
        "notes": "约 1800 张为真实叶片，其余为缩放/旋转增强；240x320 JPG。"
                 "**已被 mango_vn_kaggle 取代**：本项目需要可商用的芒果数据，"
                 "而本数据集为 NC。保留登记仅用于对照与历史引用。",
    },
    {
        "key": "mango_vn_kaggle",
        "name": "VN-MangoLeaf (Vietnam)",
        "crop": "芒果",
        "url": "https://www.kaggle.com/datasets/binhpt310/viet-nam-mango-diseases-leaves-dataset",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 7000,
        "classes": [
            "Anthracnose", "Dieback", "Gall_Midge", "Healthy",
            "Powdery_Mildew", "Red_Rust", "Sooty_Mold",
        ],
        "mapping": {
            "Anthracnose": ("芒果炭疽病", "exact"),
            "Powdery_Mildew": ("芒果白粉病", "exact"),
            "Gall_Midge": ("芒果瘿螨", "approx"),
            "Healthy": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Kaggle 下载端点无需凭据：/api/v1/datasets/download/<ref>（实测 200）",
        "notes": "2025 年越南新采集数据集，7 类各 1000 张（5551 原始 + 1449 增强，"
                 "增强图可从文件名 _crop_/_rotate_/_blur_ 识别）。"
                 "**取代 MangoLeafBD**：同样是 Anthracnose/Powdery Mildew，但许可为 CC BY 4.0。"
                 "假设其为独立采集，需对照论文确认未转载 MangoLeafBD。",
    },

    # ------------------------------------------------------------------ 荔枝
    {
        "key": "litchi_bdlitchi",
        "name": "BDLitchi",
        "crop": "荔枝",
        "url": "https://data.mendeley.com/datasets/jhb24mszdk/1",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 11094,
        "classes": [
            "Black Spot", "Burned Leaf", "Dried Leaf", "Fungal Stripe Damage",
            "Healthy Leaf", "Insect Chewing Damage", "Leaf Blight Disease",
            "Pest-Affected Dry Leaf", "Red Rust Disease", "White Spot",
            "Yellow Mosaic Virus",
        ],
        "mapping": {
            "Healthy Leaf": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Mendeley 'Download All'",
        "notes": "类别是症状描述而非病原分类，与我们的 5 个荔枝病虫害"
                 "（霜疫霉病/炭疽病/荔枝蝽/蒂蛀虫/瘿螨）无一精确对应。"
                 "数据量大但语义不可用——这是 taxonomy 不匹配最典型的例子。",
    },
    {
        "key": "litchi_leaf4001",
        "name": "LitchiLeaf4001",
        "crop": "荔枝",
        "url": "https://data.mendeley.com/datasets/f9nxr6745y/1",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": None,
        "classes": [],                    # 页面称 11 类但未列出类名
        "mapping": {},
        "verified": False,
        "verified_at": "2026-10-20",
        "access": "Mendeley 'Download All'（Files 区未在页面呈现，可能需登录）",
        "notes": "页面只写 '11 classes of leaf conditions'，未给类名，"
                 "需下载后人工核对；暂不作为候选。",
    },

    # ------------------------------------------------------------------ 槟榔
    {
        "key": "areca_kaggle",
        "name": "Arecanut Plant Disease Dataset",
        "crop": "槟榔",
        "url": "https://www.kaggle.com/datasets/sumanthsadiga/arecanut-plant-disease-dataset",
        "license": "未标注",
        "commercial_ok": None,           # 未知
        "images": 300,
        "classes": [
            "Healthy leaf", "Healthy nut", "Fruit rot", "Bud rot",
            "Yellow leaf", "Ring spot",
        ],
        "mapping": {
            "Yellow leaf": ("槟榔黄化病", "exact"),
            "Healthy leaf": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Kaggle，需账号与 API token（国内访问不稳）",
        "notes": "总量约 300 张，黄化病单类可能仅几十张，"
                 "不足以训练一个类别；且许可未标注。",
    },

    # ------------------------------------------------------------------ 香蕉
    {
        "key": "banana_kaggle",
        "name": "Banana Disease Recognition Dataset",
        "crop": "香蕉",
        "url": "https://www.kaggle.com/datasets/sujaykapadnis/banana-disease-recognition-dataset",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 408,                    # 仅原始图
        "classes": [
            "Banana Healthy Leaf", "Banana Black Sigatoka Disease",
            "Banana Panama Disease", "Banana Yellow Sigatoka Disease",
            "Banana Moko Disease", "Banana Bract Mosaic Virus Disease",
            "Banana Insect Pest Disease",
        ],
        "mapping": {
            "Banana Panama Disease": ("香蕉枯萎病", "exact"),
            "Banana Black Sigatoka Disease": ("香蕉黑星病", "exact"),
            "Banana Yellow Sigatoka Disease": ("香蕉叶斑病", "approx"),
            "Banana Healthy Leaf": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Kaggle 公开下载端点（免凭据）",
        # 增强图放在独立目录且编号与原图不对应，无法保证同一原图不跨 split，
        # 因此整体丢弃，只用 408 张原始图。
        "drop_augmented": True,
        "notes": "原始图 408 张（各类 23–86 张），增强图 2856 张已排除。"
                 "Moko / Bract Mosaic / Insect Pest 不在 v1 标签空间。",
    },
    {
        "key": "coffee_rocole_kaggle",
        "name": "RoCoLe (Robusta Coffee Leaf)",
        "crop": "咖啡",
        "url": "https://www.kaggle.com/datasets/nirmalsankalana/rocole-a-robusta-coffee-leaf-images-dataset",
        "license": "MIT",
        "commercial_ok": True,
        "images": 1560,
        "classes": ["coffee___healthy", "coffee___rust", "coffee___red_spider_mite"],
        "mapping": {
            "coffee___rust": ("咖啡锈病", "exact"),
            "coffee___healthy": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Kaggle 公开下载端点（免凭据）",
        "notes": "经典 RoCoLe 数据集。红蜘蛛 167 张不在 v1 标签空间。"
                 "原始数据论文亦提供严重度分级，后续可用于严重度头。",
    },
    {
        "key": "coffee_bracol_cls",
        "name": "BRACoL（分类视图）",
        "crop": "咖啡",
        "url": "https://www.kaggle.com/datasets/jonatanfragoso/bracol-for-yolov8-detection",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 699,
        "classes": ["Rust", "Healthy"],
        "mapping": {
            "Rust": ("咖啡锈病", "exact"),
            "Healthy": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "由 data/raw/coffee_bracol 的 YOLO 标注转换（只保留纯锈病图与无病斑图）",
        "notes": "与 RoCoLe 不同来源，用于混合来源训练；其 test 划分同时作为跨域留出集。",
    },
    {
        "key": "dragonfruit_mendeley",
        "name": "Dragonfruit-MultiOrgan (DF-MOD, Mendeley)",
        "crop": "火龙果",
        "url": "https://data.mendeley.com/datasets/kpsywfwkrf/1",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 2065,
        "classes": ["Stem_Canker", "Healthy_leaf", "Healthy_fruit"],
        "mapping": {
            "Stem_Canker": ("火龙果溃疡病", "approx"),
            "Healthy_leaf": ("健康", "exact"),
            "Healthy_fruit": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-21",
        "access": "Mendeley 公开 API 逐文件下载（需带浏览器 UA）；只取类名前缀的原始图，跳过增强图",
        "notes": "Kaggle 镜像（ohmahler91）已把类别简化为 Good/Bad，故改用 Mendeley 原版"
                 "按文件名还原类别。溃疡病为近似映射（Stem_Canker）。",
    },
    # ------------------------------------------------------------------ 香蕉（跨域）
    {
        "key": "banana_xdom",
        "name": "Banana Leaf Diseases (Uganda)",
        "crop": "香蕉",
        "url": "https://www.kaggle.com/datasets/ntambaraetienne/banana-leaf-diseases-classification-dataset",
        "license": "Apache 2.0",
        "commercial_ok": True,
        "images": 937,
        "classes": ["healthy", "sigatoka", "pestalotiopsis", "cordana"],
        "mapping": {
            "healthy": ("健康", "exact"),
            "sigatoka": ("香蕉叶斑病", "approx"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Kaggle 公开下载端点（免凭据）",
        "notes": "sigatoka 不分 Black/Yellow，只能近似映射为香蕉叶斑病；"
                 "pestalotiopsis / cordana 不在 v1 标签空间。",
    },
    # ------------------------------------------------------------------ 香蕉（Mendeley 备用源）
    {
        "key": "banana_mendeley",
        "name": "Banana and Banana Leaf Dataset",
        "crop": "香蕉",
        "url": "https://data.mendeley.com/datasets/5nfjzntwd8/1",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 3031,
        "classes": [
            "Healthy Banana Leaf", "Black Leaf Streak", "Panama Disease",
            "Banana Scab Moth", "Black Sigatoka", "Good Banana",
            "Black Pitting/Banana Rust", "Crown Rot", "Fungal Disease",
        ],
        "mapping": {
            "Panama Disease": ("香蕉枯萎病", "exact"),
            "Black Sigatoka": ("香蕉黑星病", "exact"),
            "Black Leaf Streak": ("香蕉叶斑病", "approx"),
            "Healthy Banana Leaf": ("健康", "exact"),
            "Good Banana": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Mendeley 'Download All'",
        "notes": "原始 3031 张 + 增强 15050 张。象甲、蚜虫无对应类别。",
    },

    # ------------------------------------------------------------------ 菠萝
    {
        "key": "pineapple_pldd",
        "name": "PLDD (Pineapple Leaf Disease Dataset)",
        "crop": "菠萝",
        "url": "https://zenodo.org/records/21893516",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 4476,
        "classes": ["Fusarium Rot", "Healthy Leaf", "Leaf Blight", "Mealybug Wilt"],
        "mapping": {
            "Fusarium Rot": ("菠萝心腐病", "approx"),
            "Mealybug Wilt": ("菠萝粉蚧", "approx"),
            "Healthy Leaf": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Zenodo 逐文件下载，有 MD5；约 15.8 GB",
        "notes": "心腐病实际多为疫霉属，与 Fusarium Rot 不是同一病原，"
                 "只能算 approx。黑腐病、红蜘蛛无对应。",
    },

    {
        "key": "pineapple_cand",
        "name": "Pineapple Leaf Disease Dataset（Kaggle 镜像）",
        "crop": "菠萝",
        "url": "https://www.kaggle.com/datasets/renshuddd/pineapple-leaf-disease-dataset",
        "license": "CC BY-NC-SA 4.0",
        "commercial_ok": False,
        "images": 6939,
        "classes": [
            "Pineapple_fusarium", "Pineapple_healthy",
            "Pineapple_mealybug_wilt", "Pineapple__leaf_blight",
        ],
        "mapping": {
            "Pineapple_fusarium": ("菠萝心腐病", "approx"),
            "Pineapple_mealybug_wilt": ("菠萝粉蚧", "approx"),
            "Pineapple_healthy": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-22",
        "access": "Kaggle 公开下载端点（免凭据）",
        # 原始 4,000+ 张/类会占训练集 36%，把共享特征空间拉向菠萝；
        # 限流到每类 600 张，保留类别覆盖同时降低对旧域的冲击。
        "max_per_class": 600,
        "notes": "PLDD 的 Kaggle 镜像（4 类与原版一致）。**许可为 CC BY-NC-SA，"
                 "菠萝两类不可商用**；商用版本需改用 Zenodo 原版（CC BY 4.0）。"
                 "leaf_blight 不在 v1 标签空间。每类限流 600 张。",
    },
    # ------------------------------------------------------------------ 火龙果
    {
        "key": "dragonfruit_dfmod",
        "name": "DragonFruit-MultiOrgan (DF-MOD)",
        "crop": "火龙果",
        "url": "https://data.mendeley.com/datasets/kpsywfwkrf/1",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 5468,
        "classes": [
            "Black_Rot", "Fungi", "Healthy_fruit", "Healthy_leaf",
            "Rust", "Scab", "Stem_Canker", "Sunburn",
        ],
        "mapping": {
            "Stem_Canker": ("火龙果溃疡病", "approx"),
            "Healthy_leaf": ("健康", "exact"),
            "Healthy_fruit": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Mendeley 'Download All'",
        "notes": "炭疽病、蜗牛、介壳虫无对应；Stem_Canker 与溃疡病接近但不完全等同。",
    },

    # ------------------------------------------------------------------ 木瓜
    {
        "key": "papaya_bdpapaya",
        "name": "BDPapayaLeaf",
        "crop": "木瓜",
        "url": "https://data.mendeley.com/datasets/p997fvf526/1",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 2159,
        "classes": ["Anthracnose", "BacterialSpot", "Curl", "RingSpot", "Healthy"],
        "mapping": {
            "Anthracnose": ("木瓜炭疽病", "exact"),
            "Curl": ("木瓜花叶病", "approx"),
            "Healthy": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Mendeley 'Download All'（.rar；1050 张带 XML/TXT 标注）",
        "notes": "红蜘蛛、介壳虫无对应。含病斑标注，可用于后续严重度弱监督。",
    },

    # ------------------------------------------------------------------ 椰子
    {
        "key": "coconut_agml",
        "name": "Coconut Tree Disease Dataset",
        "crop": "椰子",
        "url": "https://github.com/Project-AgML/AgML/blob/dev/docs/datasets/coconut_tree_disease_classification.md",
        "license": "未标注",
        "commercial_ok": None,
        "images": 5798,
        "classes": [
            "Bud_Root_Dropping", "Bud_Rot", "Gray_Leaf_Spot",
            "Leaf_Rot", "Stem_Bleeding",
        ],
        "mapping": {},
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "见 Data in Brief 原文（ScienceDirect 直连 403）",
        "notes": "不含红环腐病。对项目而言零可用类别。",
    },

    # ------------------------------------------------------------------ 橡胶
    {
        "key": "rubber_bdrubber",
        "name": "BDRubberLeaf",
        "crop": "橡胶",
        "url": "https://data.mendeley.com/datasets/4kjz78m7x5/1",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 1740,
        "classes": ["Anthracnose", "Dry Leaf", "Healthy Leaf", "Leaf Spot"],
        "mapping": {"Healthy Leaf": ("健康", "exact")},
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Mendeley 'Download All'",
        "notes": "不含白粉病（橡胶最常见的病害之一），零可用类别。",
    },

    # ------------------------------------------------------------------ 茶叶
    {
        "key": "tea_mendeley",
        "name": "Tea Leaf Diseases Dataset",
        "crop": "茶叶",
        "url": "https://data.mendeley.com/datasets/mkzyfj8bkj/1",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": 31265,                  # 含增强；原始约 4009
        "classes": [
            "Sunlight Scorching", "Red Spider", "Red Rust",
            "Heliopeltis", "Thrips", "Normal (Healthy)",
        ],
        "mapping": {"Normal (Healthy)": ("健康", "exact")},
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Mendeley 'Download All'",
        "notes": "不含茶饼病；且增强图占 87%，直接使用会严重高估泛化能力。",
    },

    # ------------------------------------------------------------------ 木薯
    {
        "key": "cassava_icassava",
        "name": "iCassava 2019",
        "crop": "木薯",
        "url": "https://www.tensorflow.org/datasets/catalog/cassava",
        "license": "Kaggle 竞赛条款（TFDS 未声明数据许可）",
        "commercial_ok": None,
        "images": 9430,
        "classes": [
            "Cassava Bacterial Blight (CBB)", "Cassava Brown Streak Disease (CBSD)",
            "Cassava Green Mite (CGM)", "Cassava Mosaic Disease (CMD)", "healthy",
        ],
        "mapping": {
            "Cassava Bacterial Blight (CBB)": ("木薯细菌性枯萎病", "exact"),
            "healthy": ("健康", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Kaggle 竞赛页（需登录）；或 tfds.load('cassava')",
        "notes": "5 类里 4 类与我们的标签无关，数据利用率约 40%。",
    },

    # ------------------------------------------------------------------ 咖啡
    {
        "key": "coffee_rust_severity",
        "name": "Coffee leaf rust severity segmentation",
        "crop": "咖啡",
        "url": "https://zenodo.org/records/22701350",
        "license": "CC BY 4.0",
        "commercial_ok": True,
        "images": None,
        "classes": ["Coffee leaf rust", "American leaf spot"],
        "mapping": {
            "Coffee leaf rust": ("咖啡锈病", "exact"),
        },
        "verified": True,
        "verified_at": "2026-10-20",
        "access": "Zenodo 仅存脚本归档；标注语料在 HuggingFace（链接需从页面进一步获取）",
        "notes": "**目前唯一带像素级严重度与序数分级的公开集**。"
                 "规模未知，需先拿到 HuggingFace 链接。",
    },
]


# ---------------------------------------------------------------- 下载规格
# type:
#   zenodo    通过 Zenodo 公开 API 全自动下载（含 md5 校验、自动解压 zip）
#   mendeley  Mendeley 的公开 API 只暴露扁平文件列表和 folder_id，**没有目录名**，
#             因此无法还原类别结构。必须由用户在浏览器点 "Download All"，
#             把 ZIP 放到 data/raw/<key>.zip，再由本脚本解压。
#   kaggle    需要 kaggle.json 凭据，由 kaggle CLI 下载
#   manual    无稳定自动下载方式，按 url 手工获取
DOWNLOAD_SPECS: Dict[str, dict] = {
    "mango_leaf_bd":      {"type": "mendeley", "id": "hxsnvwty3r", "zip_required": True},
    "mango_vn_kaggle":    {"type": "kaggle",
                           "slug": "binhpt310/viet-nam-mango-diseases-leaves-dataset"},
    "litchi_bdlitchi":    {"type": "mendeley", "id": "jhb24mszdk", "zip_required": True},
    "litchi_leaf4001":    {"type": "mendeley", "id": "f9nxr6745y", "zip_required": True},
    "areca_kaggle":       {"type": "kaggle", "slug": "sumanthsadiga/arecanut-plant-disease-dataset"},
    "banana_mendeley":    {"type": "mendeley", "id": "5nfjzntwd8", "zip_required": True},
    "banana_kaggle":      {"type": "kaggle",
                           "slug": "sujaykapadnis/banana-disease-recognition-dataset"},
    "banana_xdom":        {"type": "kaggle",
                           "slug": "ntambaraetienne/banana-leaf-diseases-classification-dataset"},
    "coffee_bracol_cls":  {"type": "manual",
                           "note": "由 data/raw/coffee_bracol 的 YOLO 标注转换生成"},
    "mango_xdom":         {"type": "kaggle",
                           "slug": "mdsaymonahammad/mango-leaf-disease"},
    "coffee_rocole_kaggle": {"type": "kaggle",
                             "slug": "nirmalsankalana/rocole-a-robusta-coffee-leaf-images-dataset"},
    "pineapple_cand":      {"type": "kaggle",
                            "slug": "renshuddd/pineapple-leaf-disease-dataset"},
    "pineapple_pldd":     {"type": "zenodo", "record": 21893516,
                           # Zenodo 按类别分 zip，解压时把 zip 名还原成 registry 里的类名
                           "zip_class_map": {
                               "PLDD_Fusarium": "Fusarium Rot",
                               "PLDD_Healthy": "Healthy Leaf",
                               "PLDD_Leaf_Blight": "Leaf Blight",
                               "PLDD_Mealy_bug_wilt": "Mealybug Wilt",
                           }},
    "dragonfruit_dfmod":  {"type": "mendeley", "id": "kpsywfwkrf", "zip_required": True},
    "dragonfruit_mendeley": {"type": "manual",
                             "note": "用 Mendeley 公开 API 逐文件下载并带 UA，按文件名前缀筛选类别；"
                                     "详见 docs/datasets.md"},
    "papaya_bdpapaya":    {"type": "mendeley", "id": "p997fvf526", "zip_required": True},
    "coconut_agml":       {"type": "manual", "note": "Data in Brief 原文附件，ScienceDirect 直连 403"},
    "rubber_bdrubber":    {"type": "mendeley", "id": "4kjz78m7x5", "zip_required": True},
    "tea_mendeley":       {"type": "mendeley", "id": "mkzyfj8bkj", "zip_required": True},
    "cassava_icassava":   {"type": "kaggle_competition",
                           "slug": "cassava-disease",
                           "note": "竞赛数据需接受规则；也可用 tfds.load('cassava')"},
    "coffee_rust_severity": {"type": "manual",
                             "note": "Zenodo 仅存脚本归档；标注语料在 HuggingFace，链接需从论文补充材料获取"},
}


def summary() -> Dict:
    """汇总：精确映射、近似映射、未映射类别数。"""
    exact, approx, unmapped = set(), set(), 0
    for ds in DATASETS:
        for cls in ds["classes"]:
            item: Optional[Tuple[str, str]] = ds["mapping"].get(cls)
            if item is None:
                unmapped += 1
            elif item[1] == "exact":
                exact.add(item[0])
            else:
                approx.add(item[0])
    return {
        "datasets": len(DATASETS),
        "verified_datasets": sum(1 for d in DATASETS if d["verified"]),
        "exact_labels": sorted(exact),
        "approx_labels": sorted(approx),
        "unmapped_classes": unmapped,
        "commercial_blocked": [d["key"] for d in DATASETS if d["commercial_ok"] is False],
        "license_unknown": [d["key"] for d in DATASETS if d["commercial_ok"] is None],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), ensure_ascii=False, indent=2))
