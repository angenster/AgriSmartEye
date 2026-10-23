# 数据飞轮闭环报告（P4）

> 目标：把「低置信样本回收 → 人工复核 → 增量微调 → 门禁 → 版本切换」真正跑通，
> 并验证这条链路能否在**不损害现有能力**的前提下让模型变好。
>
> 日期：2026-10-21。基座：`v1.5-papaya`（10 个训练类）。

---

## 1. 闭环实现

| 环节 | 实现 | 位置 |
|---|---|---|
| ① 触发入队 | 低置信 / CNN-VLM 分歧 / 人工标记，按图片 hash 去重 | `backend/flywheel/trigger.py` |
| ② 复核确认 | adopt / correct / reject，标签必须在模型标签空间内 | `backend/flywheel/review.py` + `/api/v1/review` |
| ③ 导出训练集 | 从 SQLite 读已确认样本，过滤非法标签与缺失文件 | `ai-model/flywheel/export_confirmed.py` |
| ④ 增量微调 | LoRA（只训分类头）+ 分层回放 + KL 蒸馏 | `ai-model/flywheel/train_lora.py` |
| ⑤ 门禁与切换 | 同域 + **跨域**非回退检查，macro-F1 用 bootstrap 显著性 | `backend/flywheel/gate.py` |

复现命令：

```bash
# 1) 模拟一批用户上传（真实场景由前端完成）
cd backend
python -m flywheel.seed_demo --dir "../ai-model/data/raw/dragonfruit_xdom/Cleaned/test/Good leaf" \
    --label 健康 --crop 火龙果 --count 150 --holdout 50 \
    --out-holdout ../ai-model/data/manifests/flywheel_holdout.json

# 2) 导出确认样本
cd ../ai-model
python flywheel/export_confirmed.py --out data/manifests/flywheel.json

# 3) LoRA 微调
python flywheel/train_lora.py --base checkpoints/v1.5-papaya/best.pt \
    --flywheel data/manifests/flywheel.json --manifest data/manifests/v1.json \
    --holdout data/manifests/flywheel_holdout.json \
    --out checkpoints/v1.6e-flywheel-distill \
    --epochs 5 --lr 3e-4 --replay-ratio 0.5 --distill-weight 1.0

# 4) 门禁（同域 + 跨域）
cd ../backend
python -m flywheel.gate --candidate ../ai-model/checkpoints/v1.6e-flywheel-distill/merged.pt \
    --tag v1.6e-flywheel-distill --base-version v1.5-papaya \
    --dataset ../ai-model/data/manifests/v1_test.json \
    --cross-domain ../ai-model/data/manifests/xdom_mango.json,../ai-model/data/manifests/xdom_coffee_et.json
```

## 2. 本次实验设置

- **飞轮样本**：150 张火龙果健康叶（来自未参与训练/评测的 Kaggle 镜像），
  模拟用户上传并复核为「健康」。选择它是因为模型在这批**新域健康图**上错得很厉害
  （200 张抽样中 128 张被判成芒果炭疽病），正是飞轮该抓的样本。
- **留出集**：同目录另取 50 张，用于评估微调后是否真的学到。
- **回放**：默认从原训练清单按类分层抽取，防止遗忘。
- **门禁**：`v1_test.json`（940 张同域）+ 芒果、埃塞俄比亚咖啡两个跨域集。

## 3. 结果：六版候选全部被门禁拒绝

| 候选 | 新域留出 | 同域 acc / F1 | 芒果跨域 | 咖啡跨域 | 门禁 |
|---|---|---|---|---|---|
| v1.5 基座 | 0.20 | 95.85% / 0.940 | 68.14% | 80.33% | production |
| v1.6（10% 回放） | **0.92** | 96.70% / 0.962 | 66.95% ↓ | 72.00% ↓ | archived |
| v1.6b（+类别权重） | 0.90 | 95.64% / 0.953 | 67.89% ↓ | 70.83% ↓ | archived |
| v1.6c（50% 回放） | 0.86 | 96.28% / 0.955 | **70.78%** ↑ | 73.33% ↓ | archived |
| v1.6d（温和 lr=1e-4） | 0.48 | 95.96% / 0.952 | **71.38%** ↑ | 77.00% ↓ | archived |
| v1.6e（+KL 蒸馏） | 0.72 | 95.85% / 0.946 | 68.82% ↑ | 75.33% ↓ | archived |
| v1.6f（+跨域回放） | 0.68 | 95.85% / 0.951 | 65.84% ↓ | **97.67%** ↑ | archived |

> v1.6f 的咖啡评测集是重新按 50/50 拆分后的 300 张，与前面几版的 600 张不可直接比较；
> 同一次门禁内 production 与 candidate 用的是同一份数据，比较有效。

**每一版都在新域上显著变好（0.20 → 0.48~0.92），但每一版都至少在某个跨域集上回退。**
门禁全部拒绝，`v1.5-papaya` 保持 production。

## 4. 关键发现

1. **单类复核批次会重塑共享特征空间。** 150 张「健康」样本让模型整体向健康偏置：
   各域健康召回上升，但咖啡锈病召回从 67% 掉到 46%~52%。这不是过拟合，
   而是分类边界随数据分布移动的必然结果。
2. **回放、类别权重、低学习率、KL 蒸馏都只能部分缓解。** 它们能保住同域指标，
   但保不住**未出现在回放集中的跨域**——KL 约束的是"见过的分布"。
3. **补上跨域回放后，被回放的域大幅提升（咖啡 81.7% → 97.7%），
   但另一个域（芒果）会回落。** 多域之间存在真实的权衡，没有免费的午餐。
4. **门禁必须同时看同域与跨域。** 旧门禁只看同域，会把 v1.6 这个
   "同域 +0.85pt、咖啡 -8.3pt" 的模型 promote 上线。

## 5. 门禁的两处改进

1. **macro-F1 改用 bootstrap 显著性检验**（详见 `docs/training.md` §3.1.2）：
   592→940 张的评测集上，固定 0.5pt 容差会把抽样噪声当成回退。
2. **新增跨域非回退检查**：`--cross-domain` 传入固定跨域清单，
   任一集准确率回退超过 0.5pt 即拒绝。同域指标会掩盖"换环境就崩"。
   门禁结果中会记录每个跨域集的 candidate/production 指标。

## 6. 结论

**飞轮链路本身已经跑通并可复现**：样本入队 → 复核 → 导出 → LoRA → 门禁 → 版本登记，
每一步都有落库记录（`sample_queue` / `sample_confirmations` / `model_versions` / `eval_runs`）。

**但单类别的复核批次不足以产出一个可上线的模型。** 正确的下一步不是继续调微调超参，
而是改变数据侧的输入：

- 复核批次必须**跨作物、跨类别均衡**（例如健康、锈病、炭疽病各占一定比例）；
- 回放集应包含**目标部署域的样本**；若目标是"适应新果园"，就需要该果园的少量标注数据；
- 或者引入**按作物/域的条件化**（例如每个域一个轻量适配器），避免共享特征空间互相拉扯。

在拿到多样化复核数据之前，飞轮应保持"收集 + 复核"状态，门禁继续拦截单类批次，
`v1.5-papaya` 作为稳定 production。
