# 智农慧眼 —— 基于AI视觉识别的热带作物病虫害精准防治系统

> 国内首个热带作物病虫害开源数据集驱动的轻量化AI精准植保解决方案

## 项目概述

**智农慧眼**是专为海南及华南热带农业设计的智能化病虫害精准防治系统。系统集成：

- **边缘计算终端**：轻量化CNN模型（<50MB，准确率>95%），Jetson Nano实时推理
- **植保无人机改装套件**：多光谱成像 + 变量精准施药系统
- **农事管理SaaS平台**：病虫害预警、智能推荐、数字化管理

## 核心创新

| 创新维度 | 技术方案 | 优势 |
|---------|---------|------|
| 数据集 | 国内首个热带作物专用开源数据集（15种作物、42种病虫害） | 高湿高温环境适应性强 |
| 模型部署 | 知识蒸馏 + 模型剪枝轻量化 | 边缘实时推理，低成本 |
| 施药方式 | 基于病情图谱的变量精准施药 | 省药30%+，环保显著 |
| 系统集成 | 感知-决策-执行-管理闭环 | 全流程智能化 |

## 项目结构

```
zhinong-huiyan/
├── frontend/          # SaaS前端（React + TypeScript + Tailwind）
├── backend/           # 后端API（FastAPI + PostgreSQL）
├── ai-model/          # AI模型（PyTorch）
│   ├── data/          # 数据集管理
│   ├── models/        # 模型架构定义
│   ├── training/      # 训练脚本
│   ├── inference/     # 推理服务
│   └── utils/         # 工具函数
├── edge-device/       # 边缘端部署（Jetson Nano）
├── drone-kit/         # 无人机改装套件控制
└── docs/              # 项目文档
```

## 快速启动

### 1. 启动后端服务

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 3. AI模型训练

```bash
cd ai-model
pip install -r requirements.txt
python training/train.py --dataset data/tropical-crops --epochs 100
```

### 4. 边缘端部署

```bash
cd edge-device
python optimize.py --model ../ai-model/models/best.pt --target jetson-nano
```

## 技术栈

| 模块 | 技术 |
|-----|------|
| 前端 | React 18, TypeScript, Tailwind CSS, ECharts, Ant Design |
| 后端 | Python, FastAPI, SQLAlchemy, PostgreSQL, Redis |
| AI模型 | PyTorch, torchvision, TensorRT, ONNX |
| 边缘端 | Jetson Nano, TensorRT, ONNX Runtime |
| 无人机 | MAVLink, DJI SDK, Multi-spectral Camera |

## 目标市场

- **核心市场**：海南热带水果产区（芒果、荔枝、槟榔），市场规模15亿元
- **扩展市场**：广西、云南、广东等亚热带作物产区

## 商业模式

- **硬件销售**：无人机改装套件 2.8万元/套（毛利率45%）
- **SaaS订阅**：1980元/年/户
- **数据服务**：病虫害预警报告、区域大数据分析

## 团队

跨学科创业团队，涵盖农业工程、计算机科学、植物保护、市场营销、软件工程、农业经济管理等专业。

## 许可协议

MIT License

---

**智农慧眼** —— 科技兴农，绿色发展，助力乡村振兴！