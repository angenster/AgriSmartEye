# 公开数据集评估与选型（D0）

> 目标：在写任何训练代码之前，先确认「42 类病虫害」这个标签空间到底有多少能被公开数据支撑。
>
> 核实日期：2026-10-20。所有类别与许可均来自原始数据集页面，未核实项已显式标注。
> 机器可读版本见 [`ai-model/data/dataset_registry.py`](../ai-model/data/dataset_registry.py)。

---

## 0. 结论（先看这里）

1. **42 类里只有 9 类能拿到精确对应的训练数据（约 21%）**；算上语义近似也只有 16 类（约 38%）。
2. **荔枝是最大的落差**：有 11,094 张图的公开数据集，但与我们的 5 个荔枝病虫害**一个都对不上**——它用的是症状名（Black Spot / Burned Leaf），不是病原名。
3. **严重度标签几乎不存在**：唯一带像素级严重度与序数分级的是咖啡锈病数据集。第三个分类头（轻/中/重）**没有训练数据**。
4. **芒果原先只能依赖 NC 数据**：MangoLeafBD 为 **CC BY-NC 3.0**，禁商用。
   已在 Kaggle 找到可商用的替代集 **VN-MangoLeaf（CC BY 4.0，7 类、7000 张）**并已采用，
   v1 全部数据均可商用。
5. 建议把 v1 的标签空间收缩到 **10–12 类**，并**暂时移除严重度头**。42 类的产品表述需要修改。

---

## 1. 数据集清单

| key | 数据集 | 作物 | 图像 | 类别 | 许可 | 商用 | 获取方式 |
|---|---|---|---|---|---|---|---|
| `mango_leaf_bd` | [MangoLeafBD](https://data.mendeley.com/datasets/hxsnvwty3r/1) | 芒果 | 4,000 | 8 | **CC BY-NC 3.0** | ❌ 已弃用 | Mendeley Download All |
| `mango_vn_kaggle` | [VN-MangoLeaf](https://www.kaggle.com/datasets/binhpt310/viet-nam-mango-diseases-leaves-dataset) | 芒果 | 7,000 | 7 | CC BY 4.0 | ✅ | Kaggle 公开端点（免凭据） |
| `mango_combined` | [Combined Mango Leaf Disease](https://www.kaggle.com/datasets/binhpt310/mango-combined-dataset) | 芒果 | 40,000 | 8 | CC BY-SA 4.0 | ❌ **已排除** | 与 MangoLeafBD 存在近重复 |
| `litchi_bdlitchi` | [BDLitchi](https://data.mendeley.com/datasets/jhb24mszdk/1) | 荔枝 | 11,094 | 11 | CC BY 4.0 | ✅ | Mendeley Download All |
| `litchi_leaf4001` | [LitchiLeaf4001](https://data.mendeley.com/datasets/f9nxr6745y/1) | 荔枝 | 未标明 | 11（未列名） | CC BY 4.0 | ✅ | Mendeley（需登录） |
| `areca_kaggle` | [Arecanut](https://www.kaggle.com/datasets/sumanthsadiga/arecanut-plant-disease-dataset) | 槟榔 | ~300 | 6 | 未标注 | ❓ | Kaggle（需 token） |
| `banana_mendeley` | [Banana & Banana Leaf](https://data.mendeley.com/datasets/5nfjzntwd8/1) | 香蕉 | 3,031 | 9 | CC BY 4.0 | ✅ | Mendeley Download All |
| `pineapple_pldd` | [PLDD](https://zenodo.org/records/21893516) | 菠萝 | 4,476（15.8 GB） | 4 | CC BY 4.0 | ✅ | Zenodo 逐文件 + MD5 |
| `pineapple_cand` | [PLDD Kaggle 镜像](https://www.kaggle.com/datasets/renshuddd/pineapple-leaf-disease-dataset) | 菠萝 | 6,939（656 MB） | 4 | **CC BY-NC-SA 4.0** | ❌ 仅研究 | Kaggle 公开端点 |
| `dragonfruit_mendeley` | [DF-MOD（Mendeley 原版）](https://data.mendeley.com/datasets/kpsywfwkrf/1) | 火龙果 | 2,065 | 3 | CC BY 4.0 | ✅ | Mendeley API 逐文件（按文件名前缀筛类） |
| `dragonfruit_xdom` | [Kaggle 镜像](https://www.kaggle.com/datasets/ohmahler91/dragon-fruit-and-leaf-dataset-from-bangladesh) | 火龙果 | 19,681 | 4（Good/Bad） | CC BY 4.0 | ⚠️ 类别已简化 | Kaggle 公开端点 |
| `papaya_bdpapaya` | [BDPapayaLeaf](https://data.mendeley.com/datasets/p997fvf526/1) | 木瓜 | 2,159 | 5 | CC BY 4.0 | ✅ | Mendeley（.rar） |
| `coconut_agml` | [Coconut Tree Disease](https://github.com/Project-AgML/AgML/blob/dev/docs/datasets/coconut_tree_disease_classification.md) | 椰子 | 5,798 | 5 | 未标注 | ❓ | 见 Data in Brief 原文 |
| `rubber_bdrubber` | [BDRubberLeaf](https://data.mendeley.com/datasets/4kjz78m7x5/1) | 橡胶 | 1,740 | 4 | CC BY 4.0 | ✅ | Mendeley Download All |
| `tea_mendeley` | [Tea Leaf Diseases](https://data.mendeley.com/datasets/mkzyfj8bkj/1) | 茶叶 | 4,009 原始（+增强） | 6 | CC BY 4.0 | ✅ | Mendeley Download All |
| `cassava_icassava` | [iCassava 2019](https://www.tensorflow.org/datasets/catalog/cassava) | 木薯 | 9,430 | 5 | Kaggle 竞赛条款 | ❓ | Kaggle / `tfds.load('cassava')` |
| `coffee_rust_severity` | [Coffee leaf rust severity](https://zenodo.org/records/22701350) | 咖啡 | 未标明 | 2 + 严重度 | CC BY 4.0 | ✅ | Zenodo（语料在 HuggingFace） |

**已排除的数据集：**

- `pineapple_cand` 不是排除，而是**按许可限制使用**：它是 PLDD 的 Kaggle 镜像
  （类别与原版一致：Fusarium / Healthy / Mealybug Wilt / Leaf Blight），
  但镜像标注为 **CC BY-NC-SA 4.0**。研究/作品集可用，**菠萝两类不可商用**；
  商用版本需改用 Zenodo 原版（CC BY 4.0，15.8 GB）。

- `mango_combined`（40,000 张、8 类）：dHash 抽查显示其 **Powdery Mildew 类有 3.6%
  （9/250）与 MangoLeafBD 近重复**（Hamming ≤3 bit，非随机碰撞）。用它训练会使
  `mango_xdom` 跨域评测失真，且许可为 CC BY-SA。已弃用。
- `jhoandorado/disease-banana`：文件名逐一比对确认是训练集香蕉数据的**完整转载**
  （469/469、602/602 同名），不可作为独立来源。

**未找到公开数据集**：胡椒（注意：搜到的 betel leaf 是蒌叶 *Piper betle*，不是胡椒 *Piper nigrum*，不可混用）、剑麻。
**未核实**：甘蔗（Data in Brief 页面 403，未能打开）、椰子（许可与类别来自 AgML 镜像页）。

---

## 2. 与 42 类的映射结果

图例：✅ 精确对应　△ 语义近似（默认不入训练集）　❌ 无对应

| 作物 | 我们的标签 | 状态 | 对应公开类别 |
|---|---|---|---|
| 芒果 | 炭疽病 | ✅ | VN-MangoLeaf `Anthracnose` |
| 芒果 | 白粉病 | ✅ | `Powdery_Mildew` |
| 芒果 | 细菌性角斑病 | △ | MangoLeafBD `Bacterial Canker`（已弃用该数据集，故不入 v1） |
| 芒果 | 瘿螨 | △ | VN-MangoLeaf `Gall_Midge`（不同类群） |
| 芒果 | 介壳虫 | ❌ | — |
| 芒果 | 蓟马 | ❌ | — |
| 荔枝 | 霜疫霉病 / 炭疽病 / 荔枝蝽 / 蒂蛀虫 / 瘿螨 | ❌ ×5 | BDLitchi 全是症状名，无病原对应 |
| 槟榔 | 黄化病 | ✅ | `Yellow leaf`（单类仅数十张，样本过少） |
| 槟榔 | 炭疽病 / 细菌性条斑病 / 红脉穗螟 / 蚧壳虫 | ❌ ×4 | — |
| 香蕉 | 枯萎病 | ✅ | `Panama Disease` |
| 香蕉 | 黑星病 | ✅ | `Black Sigatoka` |
| 香蕉 | 叶斑病 | △ | `Black Leaf Streak` |
| 香蕉 | 象甲 / 蚜虫 | ❌ ×2 | — |
| 菠萝 | 心腐病 | △ | `Fusarium Rot`（心腐多为疫霉，非同病原） |
| 菠萝 | 粉蚧 | △ | `Mealybug Wilt` |
| 菠萝 | 黑腐病 / 红蜘蛛 | ❌ ×2 | — |
| 火龙果 | 溃疡病 | △ | `Stem_Canker` |
| 火龙果 | 炭疽病 / 蜗牛 / 介壳虫 | ❌ ×3 | — |
| 木瓜 | 炭疽病 | ✅ | `Anthracnose` |
| 木瓜 | 花叶病 | △ | `Curl` |
| 木瓜 | 红蜘蛛 / 介壳虫 | ❌ ×2 | — |
| 椰子 | 红环腐病 | ❌ | 数据集只有芽腐/叶斑等 |
| 橡胶 | 白粉病 | ❌ | 数据集只有炭疽/叶斑等 |
| 胡椒 | 瘟病 | ❌ | 无数据集 |
| 咖啡 | 锈病 | ✅ | `Coffee leaf rust`（**且带严重度**） |
| 茶叶 | 茶饼病 | ❌ | 数据集只有赤锈/蓟马等 |
| 甘蔗 | 赤腐病 | ❓ | 未核实 |
| 木薯 | 细菌性枯萎病 | ✅ | `Cassava Bacterial Blight (CBB)` |
| 剑麻 | 斑马纹病 | ❌ | 无数据集 |
| — | 健康 | ✅ | 各数据集均含 healthy 类 |

**合计：精确 9 类（含"健康"）、近似 7 类、无对应/未核实 26 类。**

---

## 3. 三个硬约束

### 3.1 覆盖率：21% 精确 / 38% 含近似

不是"数据不够多"，而是**分类体系不匹配**：公开数据集多用症状描述（Black Spot、Burned Leaf、Dry Leaf），我们的标签是病原/害虫名。即使图像再多也无法直接监督。

BDPapayaLeaf 是少数例外——它带病斑标注（1050 张 XML/TXT），可用于严重度弱监督。

### 3.2 严重度标签缺失

所有数据集都是图像级分类。唯一例外是咖啡锈病严重度集（像素级分割 + 序数分级），且只覆盖 2 种病。

建议：**v1 移除 severity 头**，模型只输出 crop + disease。严重度继续由 Agent 在报告里标注"未评估"或交给 VLM/人工，而不是输出一个没有训练依据的等级。

### 3.3 许可

- **MangoLeafBD 是 CC BY-NC 3.0**：研究可用，商业不可用。而芒果是本项目的旗舰作物。
- `areca_kaggle`、`coconut_agml`、`cassava_icassava` 许可未明确，商用前必须澄清。
- 其余均为 CC BY 4.0，可商用（需署名）。

读取时的建议：数据清单里记录 `source`，报告与 README 中注明数据集与许可；商用版本只启用 `commercial_ok=True` 的条目（`build_manifest.py` 默认就是这样）。

---

## 4. 建议的 v1 标签空间

### 方案 A — 商用保守（仅精确映射 + 许可明确）

`香蕉枯萎病`、`香蕉黑星病`、`木瓜炭疽病`、`咖啡锈病`、`健康` —— **5 类**

太少，单独无法支撑演示。作为"可商用核心集"记录在案。

### 方案 B — 商用 + 近似映射（推荐给商业版本）

在 A 的基础上增加：
`香蕉叶斑病`、`木瓜花叶病`、`火龙果溃疡病`、`菠萝心腐病`、`菠萝粉蚧` —— **10 类**

### 方案 C — 允许 NC（推荐给作品集 / 研究版本）

在 B 的基础上增加：
`芒果炭疽病`、`芒果白粉病`（MangoLeafBD，CC BY-NC）—— **12 类**

> **已选定：方案 C（2026-10-20）。** 标签空间已落到
> [`ai-model/labels.py`](../ai-model/labels.py)，`LABELS_VERSION = "v1.1-research"`，
> 共 6 个作物、12 个病害类（含"健康"）。
> 芒果数据使用 **VN-MangoLeaf（CC BY 4.0）**而非 MangoLeafBD（NC），
> 因此 **v1 使用的全部数据均可商用**。

### 自采补盲（若具备田间条件）

优先级从高到低：芒果（介壳虫/蓟马）→ 荔枝（霜疫霉病/炭疽病）→ 槟榔（黄化病/炭疽病）。
每类 50–100 张即可进入训练，200 张以上更稳。拍摄要求见 §6。

---

## 5. 目录约定与清单构建

```text
ai-model/data/raw/
├── mango_leaf_bd/Anthracnose/*.jpg
├── banana_mendeley/Panama Disease/*.jpg
├── pineapple_pldd/PLDD_Healthy/*.jpg
└── ...（也支持 <dataset_key>/train/<class>/*.jpg 这种自带划分的结构）
```

构建统一清单：

```bash
cd zhinong-huiyan/ai-model

# 只看登记表（不扫文件）
python data/build_manifest.py --audit

# 生成清单（默认排除近似映射与非商用数据集）
python data/build_manifest.py --raw-root data/raw --out data/manifests/v1.json

# 作品集版本（纳入近似映射与 MangoLeafBD）
python data/build_manifest.py --raw-root data/raw --out data/manifests/v1_research.json \
    --include-approx --allow-nc
```

输出：

- `data/manifests/v1.json`：`[{"image_path", "label", "crop", "source", "source_class", "mapping_kind", "split"}]`
- `data/manifests/v1_coverage.md`：各数据集入库/丢弃统计 + 每类样本数 + 已知问题

划分是**按路径哈希确定性生成**的（80/10/10），重建清单不会改变划分，避免训练/评测泄漏。

---

## 6. 自采拍摄要求（若走补盲）

- **设备**：手机即可；固定一台，避免多设备色差被当成特征。
- **每类数量**：≥50 张/类（建议 100）。
- **多样性**：强光/阴天/雨后；早晨/正午/黄昏；叶正面/背面；近景病灶 + 中景整叶。
- **负样本**：每类同时拍健康株，避免模型把"背景/光照"学成类别。
- **元数据**：拍摄时记录 `作物 / 疑似病害 / 严重度 / 日期 / 地点 / 田块`，存成同名 CSV。
- **禁止**：使用实习公司数据；从网上抓图充数（许可与域偏移双重问题）。

---

## 7. 未核实项与下一步

未核实（需下载或换网络环境确认）：

1. `litchi_leaf4001` 的 11 个类名（页面未列出）。
2. 甘蔗赤腐病数据集（ScienceDirect 403）。
3. 椰子数据集的许可证与类别（当前来自 AgML 镜像）。
4. 咖啡锈病严重度集的 HuggingFace 地址与图像数量（Zenodo 页面只存了脚本归档）。
5. Kaggle 数据集的实际许可（`areca_kaggle`、`cassava_icassava`）。

下一步（D1）：

1. 按 §5 下载至少 5 个 CC BY 数据集，跑通 `build_manifest.py`。
2. 人工核对未核实项，更新 `dataset_registry.py` 与本文档。
3. 决定采用方案 B 还是 C，并据此修改 `ai-model/labels.py` 的标签集与 `LABELS_VERSION`。

---

## 8. D1 执行记录（2026-10-20）

### 已完成

1. **标签空间收缩到方案 C**：`labels.py` 改为 6 作物 / 12 病害类；
   原 42 类保留在 `KNOWLEDGE_CLASSES` 供 RAG 与历史数据引用。
   模型维度改为从标签表派生（`len(DISEASE_CLASSES)` / `len(CROP_CLASSES)`），
   清掉了 `lightweight_cnn.py`、`inference.py`、`prune.py` 里写死的 42/15。
2. **下载器** [`ai-model/data/download_datasets.py`](../ai-model/data/download_datasets.py)：
   Zenodo 全自动（文件列表 + md5 校验 + 断点续传 + 按类别解压）；
   Mendeley 走"浏览器 Download All → 放 ZIP → 脚本解压"；
   Kaggle 走 CLI 并给出凭据缺失时的指引。
3. **实测验证**：
   - Zenodo 下载 PLDD 的 README 与元数据 CSV，md5 校验通过；
   - 用合成 ZIP 验证 Mendeley 解压路径（3 个类目录被正确识别）；
   - 解压后 `build_manifest.py` 生成 6 条清单、3 个标签，类别映射正确；
   - 只有元数据、没有图像时，清单正确返回 0 条并标记「零可用类别」。
4. **发现 Kaggle 公开下载端点无需凭据**：`GET /api/v1/datasets/download/<ref>`
   直接返回 ZIP（实测 HTTP 200）。因此下载器改为直接调用该端点，不再依赖
   `kaggle` CLI 与 `kaggle.json`。
5. **芒果数据源更换**：从 MangoLeafBD（CC BY-NC 3.0）换成 Kaggle 上的
   **VN-MangoLeaf**（CC BY 4.0，7 类各 1000 张，5551 原始 + 1449 增强）。
   已下载并核对类别结构，生成第一份真实清单。

### 第一份真实清单（已下载的 3 个数据集）
```bash
python data/build_manifest.py --raw-root data/raw --out data/manifests/v1.json --include-approx
```

| 项 | 数值 |
|---|---|
| 入库条目 | **5,610** |
| 覆盖标签 | **8**（含 2 个近似类） |
| 划分 | train 4,497 / val 563 / test 550 |
| 跨 split 泄漏 | **0 组**（按原图 ID 分组，增强变体与原图同组） |

| 标签 | 样本数 | 来源 |
|---|---|---|
| 健康 | 1,877 | VN-MangoLeaf / RoCoLe / Banana Kaggle |
| 芒果炭疽病 | 1,000 | VN-MangoLeaf |
| 芒果白粉病 | 1,000 | VN-MangoLeaf |
| 芒果瘿螨（近似） | 1,000 | VN-MangoLeaf `Gall_Midge` |
| 咖啡锈病 | 602 | RoCoLe |
| 香蕉黑星病 | 67 | Banana Kaggle（仅原始图） |
| 香蕉枯萎病 | 41 | Banana Kaggle（仅原始图） |
| 香蕉叶斑病（近似） | 23 | Banana Kaggle（仅原始图） |

仍未覆盖：菠萝（2 类）、火龙果（1 类）、木瓜（2 类）。

### 平台限制（实测，不是推测）

- **Mendeley 公开 API 无法还原类别结构**。`/public-api/datasets/{id}` 返回 4000 个
  扁平文件，每个只有 `folder_id`，没有目录名；`/folders`、`/tree` 等端点均为 404/400。
  因此 MangoLeafBD 这类按类别分目录的数据集**必须手动下载 ZIP**。
- **Zenodo 可以全自动**，但 PLDD 共 15.8 GB，实测下载速度约 0.55 MB/s
  （单个 3.4 GB 类别包约需 1.8 小时）。

### 当前数据状态

| 数据集 | 状态 |
|---|---|
| `mango_vn_kaggle` | ✅ 已下载，4,000 条入库 |
| `coffee_rocole_kaggle` | ✅ 已下载，1,393 条入库 |
| `banana_kaggle` | ✅ 已下载，217 条入库（2,856 张增强图因无法防泄漏而丢弃） |
| `pineapple_pldd` | 已下载元数据（CSV + README），图像未下载（15.8 GB） |
| `dragonfruit_dfmod` / `papaya_bdpapaya` | 待下载（火龙果 4.8 GB；木瓜需 Mendeley ZIP） |

### 下一步需要手动完成的部分

Kaggle 数据集直接跑 `download_datasets.py` 即可，无需登录：

```bash
python data/download_datasets.py --only mango_vn_kaggle
```

仍需浏览器下载的只有 Papaya（Mendeley）：

| 数据集 | 期望文件名 | 大小（约） |
|---|---|---|
| BDPapayaLeaf | `papaya_bdpapaya.zip` | 数百 MB |
| Banana & Banana Leaf | `banana_mendeley.zip` | 数百 MB |
| DragonFruit-MultiOrgan | `dragonfruit_dfmod.zip` | 数 GB |
| MangoLeafBD | `mango_leaf_bd.zip` | 134 MB |
| BDRubberLeaf / Tea | 可跳过（对 v1 标签无贡献） | — |

放好后运行：

```bash
cd zhinong-huiyan/ai-model
python data/download_datasets.py --only papaya_bdpapaya,banana_mendeley,mango_leaf_bd,dragonfruit_dfmod
python data/build_manifest.py --raw-root data/raw --out data/manifests/v1_research.json \
    --include-approx --allow-nc
```

即可得到第一份真实清单与覆盖率报告。

---

## 9. 来源

- MangoLeafBD: <https://data.mendeley.com/datasets/hxsnvwty3r/1>
- BDLitchi: <https://data.mendeley.com/datasets/jhb24mszdk/1>
- LitchiLeaf4001: <https://data.mendeley.com/datasets/f9nxr6745y/1>
- Arecanut: <https://www.kaggle.com/datasets/sumanthsadiga/arecanut-plant-disease-dataset>
- Banana: <https://data.mendeley.com/datasets/5nfjzntwd8/1>
- PLDD: <https://zenodo.org/records/21893516>
- DragonFruit-MultiOrgan: <https://data.mendeley.com/datasets/kpsywfwkrf/1>
- BDPapayaLeaf: <https://data.mendeley.com/datasets/p997fvf526/1>
- Coconut: <https://github.com/Project-AgML/AgML/blob/dev/docs/datasets/coconut_tree_disease_classification.md>
- BDRubberLeaf: <https://data.mendeley.com/datasets/4kjz78m7x5/1>
- Tea Leaf Diseases: <https://data.mendeley.com/datasets/mkzyfj8bkj/1>
- iCassava 2019: <https://www.tensorflow.org/datasets/catalog/cassava>
- Coffee leaf rust severity: <https://zenodo.org/records/22701350>
- PDDD-PreTrain（可选预训练骨干）: <https://www.sciencedirect.com/science/article/pii/S2643651524001778>
