# 会话交接文档（HANDOFF）

> 更新时间：2026-10-23。用途：在新会话 / compact 之后快速恢复上下文。
> 本文件只记录"当前状态、决策与未完成项"，详细过程见 `docs/` 下的专题文档。

---

## 1. 一句话现状

智农慧眼已完成方案 P0–P4：诊断 Agent、RAG、复核队列、数据飞轮、评测门禁全部落地，
当前 production 是 **v1.5-papaya**（10 个训练类，同域 95.85% / macro-F1 0.940，
真跨域芒果 68.14% / 咖啡 81.67%）。菠萝数据已获取，回退根因已定位但**暂不上线**（见 §5）。

## 2. 关键路径

| 内容 | 位置 |
|---|---|
| 后端（FastAPI） | `zhinong-huiyan/backend/` |
| 前端（React） | `zhinong-huiyan/frontend/` |
| 模型与训练 | `zhinong-huiyan/ai-model/` |
| 标签定义（单一事实来源） | `ai-model/labels.py`（v1.1-research，12 类） |
| 当前生产权重 | `ai-model/checkpoints/best.pt`（= v1.5-papaya） |
| 数据清单 | `ai-model/data/manifests/v1.json`（gitignored，需重建） |
| 数据集登记表 | `ai-model/data/dataset_registry.py` |
| 农药登记库（query_pesticide 数据源） | `backend/pesticide/registry.py` + `models.PesticideEntry`（表 `pesticide_registry`） |
| 训练/跨域/飞轮报告 | `docs/training.md`、`docs/cross_domain_eval.md`、`docs/flywheel.md`、`docs/datasets.md` |

## 3. 版本链（数据库 `model_versions`）

| 版本 | 状态 | 说明 |
|---|---|---|
| v1.1-research | archived | 单来源基线 |
| v1.2-mixed | archived | 加入 BRACoL + 乌干达香蕉 |
| v1.3-dr | archived | 域随机化增强 |
| v1.4-dragonfruit | archived | 加入火龙果 |
| **v1.5-papaya** | **production** | 加入木瓜 + 作物一致性约束 |
| v1.6~v1.6f | archived | 飞轮六版候选，均因跨域回退被拒 |
| v1.7 / v1.7b | archived | 加入菠萝，因芒果跨域回退被拒 |

## 4. 关键决策（不要再走回头路）

1. **标签空间**：12 类（6 作物 + 健康），`LABELS_VERSION="v1.1-research"`。
   原 42 类保留在 `KNOWLEDGE_CLASSES`，供 RAG 与历史数据引用。
2. **推理时屏蔽零样本类别**：权重里记录 `trained_classes`，未训练的类概率置零。
3. **作物一致性约束**：病害必须与预测作物一致（`MODEL_CROP_CONSISTENCY`，默认开）。
4. **门禁**：
   - 准确率用 0.5pt 固定容差；
   - macro-F1 用 bootstrap 显著性检验（小评测集上固定阈值不可靠）；
   - `--cross-domain` 传入固定跨域清单，任一集回退即拒绝。
5. **飞轮**：单类别复核批次会重塑共享特征空间，必须跨作物/跨类别均衡才能上线。
6. **许可**：芒果 VN-MangoLeaf（CC BY 4.0）、木瓜/火龙果（CC BY 4.0）、咖啡（MIT/CC BY）、
   香蕉（CC BY/Apache）、**菠萝镜像为 CC BY-NC-SA，不可商用**。
7. **新增作物前先保证已有作物的跨域鲁棒性**：跨域芒果有 18% 在特征空间与菠萝重叠，
   任何包含菠萝类的分类器都会损失这部分样本（详见 §5.1）。不要把回退误判成
   “病害头被污染”而去分支病害头。
8. **用药数据只来自 `pesticide_registry`**：`query_pesticide` 查表返回，禁止模型生成。
   未校审条目（`verified=false`）只返回药品名与登记信息、**不下发剂量**；
   已校审条目必须带 `dosage` 才允许入库（导入时强制校验）。
9. **诊断 Agent 有两个入口**：`POST /agent/diagnose`（同步）与
   `POST /agent/diagnose/stream`（SSE，前端实时渲染思考时间线）。两者共用
   `run_agent` 与同一套落库逻辑，不要只改其中一个。

## 5. 未完成项（按优先级）

1. **菠萝受阻（根因已定位，暂不推进）**：详见 `docs/training.md` §3.1.6。
   v1.7/v1.7b 把同域提到 96.8~97.2%，但芒果跨域从 68.14% 掉到 55.4~59.6%，门禁拒绝。
   分层诊断：病害头**没有**退化（作物判对时 65.1% vs v1.5 的 66.2%），缺口全部来自
   作物头把芒果判成菠萝（6.7%→24.9%）。冻结特征线性探针显示 **18.3% 的跨域芒果在
   特征空间里就与菠萝重叠**。后处理（软作物先验 / 病害反推作物 / 新类置信度阈值）
   最多恢复到 60.5%，门禁要求 ≥67.64%。
   **不要再实现“按作物分支的病害头”**——病害头是好的，分支解决不了作物头混淆。
   解锁条件：新增许可合规的芒果域多样性来源。商用路线还需把菠萝数据换成
   `pineapple_pldd`（CC BY 4.0）——当前 `pineapple_cand` 为 CC BY-NC-SA，仅研究可用。
2. **内容安全（已定为产品边界）**：
   - **不提供化学用药建议**：仓库内没有经人工校核的农药登记数据，未校审条目只给药名
     与登记信息、不下发剂量；对外表述统一为“诊断 + 非化学防治”。README §4.1 已写明。
   - RAG 42 条语料仍全部是 `ai_draft_unreviewed`。初审报告见
     `docs/corpus_review.md`（10 条需重点核对，其中甘蔗赤腐病病原、椰子红环腐病
     病因表述风险较高）。校对登记与回填工具：`python -m rag.review_corpus`。
   - 2026-10-23 完成一轮**有出处的 AI 复核**：只覆盖模型可触达的 12 条，修正了病原名
     与流行条件并补充 `sources`；明细见 `docs/corpus_ai_review.md`。这**仍不是人工校审**，
     `reviewed` 保持 false，索引已重建。人工签字仍需植保人员。
3. **后端不常驻**：需要时按 §6 启动；`checkpoints/best.pt` 为 v1.5。
4. 本轮语料校对工具与初审报告尚未提交（`git status` 可查看）。

## 6. 常用命令

```bash
# 启动后端（首次启动约 100 秒，含模型 + RAG 重排预热）
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m uvicorn main:app --port 8000
```

```bash
# 启动前端
cd zhinong-huiyan/frontend && npm run dev
```

```bash
# 导入农药登记样例（全部标记未校审；可重复执行，按记录去重）
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m pesticide.registry --seed

# 生成空白模板 / 只校验不写库 / 导入真实数据
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m pesticide.registry \
    --template ../docs/pesticide_data.csv
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m pesticide.registry \
    --check ../docs/pesticide_data.csv
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m pesticide.registry \
    --file ../docs/pesticide_data.csv

# 查看库中条目
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m pesticide.registry --list
```

```bash
# 语料人工校对：导出 → 专家填写 → 回填 → 重建索引
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m rag.review_corpus \
    --export ../docs/corpus_review.csv
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m rag.review_corpus \
    --apply ../docs/corpus_review.csv
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m rag.indexer
```

```bash
# 重建数据清单（需先有 data/raw/ 下的数据集）
cd zhinong-huiyan/ai-model && python data/build_manifest.py --raw-root data/raw \
    --out data/manifests/v1.json --include-approx --allow-nc
```

```bash
# 训练
cd zhinong-huiyan/ai-model && python training/train_manifest.py \
    --manifest data/manifests/v1.json --epochs 10 --batch-size 32 --img-size 224 \
    --aug dr --out checkpoints/<tag>
```

```bash
# 门禁（同域 + 跨域）
cd zhinong-huiyan/backend && python -m flywheel.gate \
    --candidate ../ai-model/checkpoints/<tag>/best.pt --tag <tag> \
    --dataset ../ai-model/data/manifests/v1_test.json \
    --cross-domain ../ai-model/data/manifests/xdom_mango.json,../ai-model/data/manifests/xdom_coffee_et.json
```

```bash
# 跨域评测
cd zhinong-huiyan/ai-model && python training/eval_cross_domain.py \
    --weights checkpoints/<tag>/best.pt
```

```bash
# 生成 CNN 基线指标报告（会加载生产权重在门禁评测集上重跑）
cd zhinong-huiyan/ai-model && python training/make_cnn_metrics.py
# 只汇总已有 metrics.json / 跨域报告，不加载模型
cd zhinong-huiyan/ai-model && python training/make_cnn_metrics.py --skip-eval
```

```bash
# Agent 级评测（逐张跑完整诊断，产出 ai-model/reports/agent_metrics.md）
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m flywheel.eval_agent \
    --per-class 10
```

```bash
# 单元测试（农药导入校验、语料校对、SSE 事件顺序）
cd zhinong-huiyan/backend && ./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## 7. 改造方案验收状态（2026-10-23 核对）

| 阶段 | 验收项 | 状态 |
|---|---|---|
| P0 | 去 Mock、接真实推理、最小可用权重 | ✅ |
| P0 | `reports/cnn_metrics.md` 产物 | ✅ 由 `training/make_cnn_metrics.py` 生成，含原始与生产推理路径两套口径 |
| P1 | ReAct / 6 工具 / 双引擎仲裁 / 证据核对 / 成本落库 | ✅ |
| P1 | SSE 流式接口 | ✅ `POST /api/v1/agent/diagnose/stream` |
| P1 | Agent 级评测 | ✅ 96 张：Agent 94.79%、升级率 6.25%、needs_human 4.17%、证据核对 100%；无 VLM 密钥，相对 CNN 增益为 0（`ai-model/reports/agent_metrics.md`） |
| P2 | 42 类语料 + 混合检索（Recall@5 > 0.8） | ⚠️ 检索达标；12 条可触达条目已做有出处的 AI 复核，仍待人工签字（`docs/corpus_ai_review.md`） |
| P2 | 农药登记表 + `query_pesticide` | ✅ 表、导入管道、检索已就绪；**产品边界：无已校核数据，不提供化学用药** |
| P3 | 飞轮最小闭环 | ✅ |
| P4 | LoRA 微调 + 门禁报告 | ✅ v1.6~v1.6f 六版 candidate 有完整记录 |
| P4 | README 数字同步 | ✅ 已按实际指标、技术栈与边界重写 |
| P4 | 演示素材固化 | ✅ `data/demo/e2.json` 固定 24 张（含 4 张难例），流程见 `docs/demo.md` |
| — | 自动化测试 | ✅ 17 个 unittest：农药导入校验、语料校对、SSE 事件顺序（`backend/tests/`） |

> `cnn_metrics.md` 里的 95.85% 是“仅训练类”口径（940 张：病害与作物都在训练范围内）。
> 当前 `v1_test.json` 已重建为 1122 张，含菠萝的 2 个未训练病害类与 74 张菠萝健康图；
> 直接算全量会得到 85.83%，那是能力缺口，不是回归。两套口径报告里都有。

仍在方案范围内的缺口：

- **RAG 语料人工签字**（需要植保人员）；
- **VLM 升级路径未实测**：没有 `VLM_API_KEY`，升级尝试全部失败。评测显示被仲裁规则
  挑出的 6 张难例准确率只有 33%，这正是双引擎该发挥作用的地方，但没有密钥无法验证增益；
- **`pest_info` 表 0 行**：42 条语料直接建在 `knowledge_chunks`，功能等价但与该表无关。

## 8. 环境注意

- 必须用 `backend/.venv`（Python 3.11）。系统默认 Python 3.14 没有 torch。
- HuggingFace 需要 `HF_ENDPOINT=https://hf-mirror.com`（代码已默认）。
- Mendeley API 下载需带浏览器 UA，否则 403。
- Windows 上服务进程会锁 `.pyd/.dll`，装包前先停服务。
- 详细坑位见记忆文件 `agrismarteye-env-quirks.md`。
