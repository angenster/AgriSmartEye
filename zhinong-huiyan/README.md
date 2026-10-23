# 智农慧眼 —— 热带作物病虫害诊断 Agent

> 拍一张叶片照片，诊断 Agent 自主完成「CNN 快筛 → 按需升级多模态模型 → RAG 查证」，
> 输出带结构化证据的诊断报告；拿不准的样本自动进入复核队列，驱动模型迭代。

## 1. 项目现状

智农慧眼已完成诊断 Agent、RAG 检索、复核队列、数据飞轮与评测门禁的工程实现，
当前生产模型为 **v1.5-papaya**（6 作物 / 12 个病害类，其中 10 类有训练数据）。

这不是一个已经可以下地使用的成品。下面「系统边界」一节列出了明确的能力边界，
对外表述请以实际指标和边界为准。

## 2. 核心能力

| 能力 | 实现 |
|---|---|
| 诊断 Agent | 手写 ReAct 循环（≤12 步），白名单工具，双引擎仲裁；规则 planner 默认可用，配置 `LLM_API_KEY` 后启用 LLM planner |
| 双引擎感知 | CNN 全量快筛；低置信或 top1-top2 间距不足时按需升级 VLM（`VLM_API_KEY`） |
| 报告 | 结构化 `DiagnosticReport`，每条判断挂可程序核对的证据（CNN / VLM / RAG chunk / 农药登记条目） |
| 流式诊断 | `POST /api/v1/agent/diagnose/stream`，前端实时渲染思考时间线 |
| RAG | 42 类病虫害知识条目，FTS5 + 向量检索 + RRF + 重排 |
| 数据飞轮 | 低置信样本入队 → 人工复核 → LoRA 微调 → 同域 + 跨域门禁 → 版本登记 |
| 前端 | React 18 + TypeScript，识别、复核、看板、田块、知识库等页面全部接真实 API |

## 3. 模型指标（v1.5-papaya）

| 评测集 | 样本 | 准确率 | macro-F1 | 说明 |
|---|---|---|---|---|
| 同域测试集（门禁） | 940 | **95.85%** | **0.940** | 与训练数据同来源 |
| 芒果跨域（孟加拉） | 1,174 | **68.14%** | 0.689 | 未参与训练，真跨域 |
| 咖啡跨域（埃塞俄比亚） | 600 | **80.33%** | 0.803 | 未参与训练，真跨域 |

**同域 95.85% 不代表田间可用。** 换个国家、换台手机、换片果园，芒果会掉到 68%。
对外演示时两组数字必须同时给出。评测方法与逐类明细见
[`docs/cross_domain_eval.md`](docs/cross_domain_eval.md)，完整口径（训练脚本原始
argmax、生产推理路径、逐类召回）见
[`ai-model/reports/cnn_metrics.md`](ai-model/reports/cnn_metrics.md)。

## 4. 系统边界与已知限制

### 4.1 不提供化学用药建议（产品边界）

**系统当前不提供具体的化学药剂与剂量建议。** 原因与规则：

- 药品名称与剂量只能来自农药登记库，**不允许模型生成**（用药安全红线）。
- 仓库内没有经过人工校核的农药登记数据；现有的 6 条样例全部标记为未校审。
- 未校审条目最多只显示药品名与登记信息，`dosage` 恒为空，并明确提示
  “需人工核对后提供”；查不到条目时，Agent 直接说明不提供用药建议。
- 在接入已校核的农药登记数据之前，请把产品能力表述为
  **“诊断 + 非化学防治（农业/物理措施）”**，不要使用“精准施药”“推荐用量”等表述。

接入真实数据后，系统会自动启用剂量：导入时强制要求 `verified=true` 的条目
必须带 `dosage` 与来源。采集与导入规范见 [`docs/pesticide_data.md`](docs/pesticide_data.md)。

### 4.2 其他限制

| 限制 | 现状 |
|---|---|
| 知识库语料 | 42 条全部为 AI 起草、未经植保人员校对，检索结果与报告中会标注 `ai_draft_unreviewed`。模型可触达的 12 条已做一轮有出处的 AI 复核（[`docs/corpus_ai_review.md`](docs/corpus_ai_review.md)），但仍未人工签字；初审与签字流程见 [`docs/corpus_review.md`](docs/corpus_review.md) |
| 严重度 | 公开数据无严重度标注，模型不训练严重度头；报告显示“未评估” |
| 菠萝 | 数据已获取，但加入后芒果跨域从 68.14% 掉到 55~60%，门禁拒绝，暂未上线 |
| 真实田间数据 | 尚未采集；现有指标全部来自公开数据集 |
| 病斑定位 | 图像级分类，不输出 bbox |
| 自动化测试 | 17 个 unittest，覆盖农药导入校验、语料校对与 SSE 事件顺序 |

## 5. 快速启动

### 5.1 后端

```bash
cd zhinong-huiyan/backend

# 首次使用：创建虚拟环境并安装依赖（Python 3.11）
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt

# 启动（首次约 100 秒，含模型加载与 RAG 重排预热）
./.venv/Scripts/python.exe -m uvicorn main:app --port 8000
```

后端默认使用 SQLite（`backend/zhinong.db`），无需 PostgreSQL。
接口文档：<http://localhost:8000/docs>。模型状态探针：`GET /health/model`。

### 5.2 前端

```bash
cd zhinong-huiyan/frontend
npm install
npm run dev
```

访问 <http://localhost:3000>。Vite 已把 `/api` 与 `/uploads` 代理到 8000 端口。

### 5.3 模型与数据

```bash
# 重建数据清单（需先准备 ai-model/data/raw/ 下的数据集）
cd zhinong-huiyan/ai-model
python data/build_manifest.py --raw-root data/raw --out data/manifests/v1.json \
    --include-approx --allow-nc

# 训练
python training/train_manifest.py --manifest data/manifests/v1.json \
    --epochs 10 --batch-size 32 --img-size 224 --aug dr --out checkpoints/<tag>
```

生产权重：`ai-model/checkpoints/best.pt`（= v1.5-papaya）。

## 6. 5 分钟演示口径

1. **（30 秒）定位**：这不是一个通用植保问答，而是一个会调用工具、给证据、
   知道自己不确定的**诊断 Agent**。
2. **（90 秒）跑一次诊断**：登录后上传叶片图，切到「Agent 诊断」。
   展示实时思考时间线：CNN 快筛 → 是否升级 → 检索知识 → 查登记农药。
3. **（60 秒）讲证据与成本**：报告里每条判断都有 `ref`（CNN 检测记录、
   knowledge_chunks、pesticide_registry），程序逐条核对；成本字段记录 VLM 调用次数、
   LLM token 与总耗时。
4. **（60 秒）讲边界**：明确说明**系统不提供化学用药剂量**，原因是登记数据未经校核；
   同时给出同域 95.85% 与跨域 68.14%/80.33% 两组数字，不夸大泛化能力。
5. **（60 秒）讲飞轮**：低置信样本自动进入复核队列，人工确认后走 LoRA 微调 + 门禁；
   六版候选均因跨域回退被拒，说明门禁在起作用。

演示时不要使用“准确率 95%”“精准施药”“省药 30%”这类脱离上下文的表述。

## 7. 技术栈

| 模块 | 技术 |
|---|---|
| 后端 | Python 3.11、FastAPI、SQLAlchemy、SQLite（WAL） |
| 前端 | React 18、TypeScript、Tailwind CSS、Ant Design、ECharts |
| 模型 | PyTorch、torchvision、MobileNetV3-Small（约 5.6 MB） |
| 检索 | jieba、SQLite FTS5、sqlite-vec、bge-small-zh / bge-reranker |
| 增量训练 | peft LoRA、分层回放、KL 蒸馏 |
| 部署 | uvicorn + Vite；docker-compose 为预留配置 |

## 8. 目录结构

```
zhinong-huiyan/
├── backend/          # FastAPI：agent/、rag/、flywheel/、pesticide/、routers/
├── frontend/         # React + TypeScript
├── ai-model/         # 模型、训练、评测、数据清单与权重
├── docs/             # 交接、训练、跨域评测、飞轮、语料与数据文档
└── edge-device/      # 边缘端实验代码（未接入主链路）
```

`drone-kit/` 为无人机改装套件的早期原型，未接入主链路；本项目不连接、不控制真实无人机。

## 9. 文档索引

| 文档 | 内容 |
|---|---|
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | 当前状态、决策、未完成项与常用命令 |
| [`docs/training.md`](docs/training.md) | 训练版本、回退诊断与结论 |
| [`docs/cross_domain_eval.md`](docs/cross_domain_eval.md) | 跨域评测方法与逐类结果 |
| [`docs/flywheel.md`](docs/flywheel.md) | 数据飞轮闭环与六版候选结果 |
| [`docs/pesticide_data.md`](docs/pesticide_data.md) | 农药登记数据采集、导入与校核规范 |
| [`docs/corpus_review.md`](docs/corpus_review.md) | 语料初审报告与校对流程 |
| [`docs/demo.md`](docs/demo.md) | 固定演示集与演示流程 |
| [`ai-model/reports/agent_metrics.md`](ai-model/reports/agent_metrics.md) | Agent 级评测：准确率、升级率、needs_human 与证据核对率 |

## 10. 目标市场与商业模式（规划）

以下为项目规划，不代表当前已具备的交付能力：

- **核心市场**：海南热带水果产区（芒果、荔枝、槟榔等）
- **扩展市场**：广西、云南、广东等亚热带作物产区
- **收入设想**：SaaS 订阅、区域病虫害预警报告、与植保服务商合作

## 11. 许可协议

MIT License。
