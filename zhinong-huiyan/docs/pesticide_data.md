# 农药登记数据：收集与导入说明

> 目的：在没有现成数据文件的情况下，用最小成本建立**可溯源、可核对**的农药登记库。
> 数据来源必须是官方登记信息或农药标签，不能来自二手文章、电商页面或模型记忆。

## 1. 只做最小可用集

12 类模型标签里，10 个训练类对应 11 个病害。按“每个病害 2–3 个登记产品”
计算，**20–30 条**就足以覆盖主要诊断结果，不需要一次做全。

| 作物 | 病害 |
|---|---|
| 芒果 | 芒果炭疽病、芒果白粉病 |
| 香蕉 | 香蕉枯萎病、香蕉黑星病、香蕉叶斑病 |
| 菠萝 | 菠萝心腐病、菠萝粉蚧 |
| 火龙果 | 火龙果溃疡病 |
| 木瓜 | 木瓜炭疽病、木瓜花叶病 |
| 咖啡 | 咖啡锈病 |

**注意：查不到登记药剂是正常结果。** 木瓜花叶病是病毒病，没有化学治疗药剂；
香蕉枯萎病以抗病品种和土壤管理为主。这些病害在库里留空，`query_pesticide`
返回 `pesticide_not_found`，Agent 会明确说明“不提供用药建议”——这是正确行为，
不要为了凑数据硬填。

## 2. 去哪里查

1. **中国农药信息网**（农业农村部农药检定所）的农药登记查询：按“作物 / 防治对象”
   检索，能看到登记证号、有效成分、剂型、登记作物与防治对象、用药量。
2. **农药标签**：剂量与安全间隔期以登记核准标签为准，登记查询里没有的字段去标签找。
3. 省级农业农村部门的登记公告可作为补充。

抄录时保留官网原文，**不要换算单位**（“稀释 1500–2000 倍”就照抄，
不要改写成百分比）。

## 3. 字段怎么填

| 字段 | 说明 | 必填 |
|---|---|---|
| `crop_type` | 作物名，必须在 `CROP_CLASSES` 内（芒果/香蕉/菠萝/火龙果/木瓜/咖啡） | 建议 |
| `disease_name` | 病害名，必须与 `DISEASE_CLASSES` 完全一致 | 是 |
| `product_name` | 登记农药名称（含含量，如“45%咪鲜胺水乳剂”） | 是 |
| `active_ingredient` | 有效成分 | 建议 |
| `formulation` | 剂型（水乳剂、悬浮剂、可湿性粉剂…） | 建议 |
| `dosage` | 用药量，照抄登记信息或标签原文 | 校审通过时必填 |
| `safe_interval_days` | 安全间隔期，整数天 | 建议 |
| `registration_no` | 农药登记证号（如 PD…） | 建议 |
| `manufacturer` | 登记证持有人 | 否 |
| `source` | 来源名称，如“中国农药信息网” | 是 |
| `source_url` | 查询结果页或公告地址 | 建议 |
| `verified` | 是否已人工核对登记信息/标签 | 是 |
| `notes` | 核对人、日期、存疑点 | 否 |

校验规则（导入时强制）：

- `verified=true` 必须有 `dosage`，否则拒绝入库；
- `source` 不能为空；
- 同一 `(crop_type, disease_name, product_name, formulation)` 视为同一条，
  默认跳过，`--replace` 时更新。

## 4. 操作步骤

```bash
cd zhinong-huiyan/backend

# 1) 生成空模板
./.venv/Scripts/python.exe -m pesticide.registry --template ../docs/pesticide_data.csv

# 2) 按第 2、3 节收集并填写

# 3) 只校验，不写库
./.venv/Scripts/python.exe -m pesticide.registry --check ../docs/pesticide_data.csv

# 4) 校验通过后导入
./.venv/Scripts/python.exe -m pesticide.registry --file ../docs/pesticide_data.csv

# 5) 查看结果
./.venv/Scripts/python.exe -m pesticide.registry --list
```

## 5. 复核要求

`verified=true` 表示**有人对照官方登记信息或标签逐条核对过**，不是“看起来合理”。
建议：

- 至少两人独立核对高风险项（高价值作物、常用药）；
- 在 `notes` 写明核对依据与日期，便于追溯；
- 剂量、安全间隔期、登记作物三者任一存疑，就保持 `verified=false`。

未校审条目在系统中只显示药品名与登记信息，**不下发剂量**；报告会明确提示
“需人工核对后提供”。这是刻意的安全设计，不要绕过。
