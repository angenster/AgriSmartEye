# 智农慧眼部署指南

## 系统要求

### 服务器端

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 4核 | 8核+ |
| 内存 | 8GB | 16GB+ |
| 存储 | 50GB SSD | 100GB SSD |
| GPU | 可选 | NVIDIA T4/V100 |
| 网络 | 10Mbps | 100Mbps+ |

### 边缘端 (Jetson Nano)

| 组件 | 要求 |
|------|------|
| 设备 | NVIDIA Jetson Nano 4GB |
| 系统 | JetPack 4.6+ (Ubuntu 18.04) |
| CUDA | 10.2 |
| cuDNN | 8.0 |
| TensorRT | 7.1+ |
| 存储 | 64GB microSD |
| 摄像头 | CSI/USB 摄像头 |

## Docker Compose部署（推荐）

### 1. 环境准备

```bash
# 安装 Docker
sudo apt update
sudo apt install -y docker.io docker-compose

# 启动 Docker
sudo systemctl start docker
sudo systemctl enable docker

# 克隆项目
git clone https://github.com/your-org/zhinong-huiyan.git
cd zhinong-huiyan
```

### 2. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 3. 初始化数据库

```bash
# 进入后端容器
docker-compose exec backend bash

# 运行数据库迁移
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"

# 创建管理员账户
python -c "
from database import SessionLocal
from models import User
from routers.auth import get_password_hash
db = SessionLocal()
admin = User(
    username='admin',
    email='admin@zhinong.com',
    hashed_password=get_password_hash('admin123'),
    full_name='系统管理员',
    role='admin'
)
db.add(admin)
db.commit()
"
```

### 4. 访问服务

- **前端界面**: http://localhost:3000
- **API文档**: http://localhost:8000/docs
- **API端点**: http://localhost:8000/api/v1

## 手动部署

### 前端部署

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build

# 使用 Nginx 部署
cp -r dist /var/www/zhinong
# 配置 Nginx 指向 dist 目录
```

### 后端部署

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Nginx反向代理配置

```nginx
server {
    listen 80;
    server_name zhinong.yourdomain.com;

    # 前端
    location / {
        root /var/www/zhinong;
        try_files $uri $uri/ /index.html;
    }

    # API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket (如需)
    location /ws/ {
        proxy_pass http://localhost:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 边缘端部署

### Jetson Nano准备

```bash
# 1. 刷写JetPack镜像
# 下载 JetPack 4.6.1 SD卡镜像
# 使用 Etcher 刷写到 64GB SD卡

# 2. 系统配置
sudo apt update
sudo apt upgrade -y

# 3. 安装系统依赖
sudo apt install -y \
    python3-pip python3-dev \
    libopenblas-base libopenmpi-dev \
    libomp-dev libjpeg-dev zlib1g-dev

# 4. 安装PyTorch (Jetson专用)
wget https://nvidia.box.com/shared/static/fjtbno0vpo676a25cgvuqc1wty0fkkg6.whl -O torch.whl
pip3 install torch.whl

# 5. 安装TorchVision
wget https://nvidia.box.com/shared/static/2zc36aTrARjB6p6nRt5n2U2d8x9b3U7E.whl -O torchvision.whl
pip3 install torchvision.whl

# 6. 安装TensorRT
# JetPack已预装，检查版本
dpkg -l | grep tensorrt
```

### 模型优化与部署

```bash
cd edge-device

# 1. 优化模型（导出ONNX + TensorRT）
python optimize.py \
    --model ../ai-model/checkpoints/best_model.pth \
    --output-dir ./optimized \
    --img-size 224 \
    --fp16

# 2. 运行边缘推理
python deploy.py \
    --model ./optimized/zhinong.onnx \
    --backend onnx \
    --source 0 \
    --show

# 或使用TensorRT
python deploy.py \
    --model ./optimized/zhinong.trt \
    --backend tensorrt \
    --source 0 \
    --show
```

### 系统服务配置

创建 systemd 服务：`/etc/systemd/system/zhinong-edge.service`

```ini
[Unit]
Description=智农慧眼边缘推理服务
After=network.target

[Service]
Type=simple
User=jetson
WorkingDirectory=/home/jetson/zhinong-huiyan/edge-device
ExecStart=/usr/bin/python3 /home/jetson/zhinong-huiyan/edge-device/deploy.py \
    --model /home/jetson/models/zhinong.onnx \
    --backend onnx \
    --source 0 \
    --mqtt
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl enable zhinong-edge
sudo systemctl start zhinong-edge
sudo systemctl status zhinong-edge
```

## 模型训练部署

### 环境准备

```bash
cd ai-model

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 数据准备

```bash
# 数据集目录结构
data/
├── train/
│   ├── 芒果/
│   │   ├── 炭疽病/
│   │   ├── 白粉病/
│   │   └── 健康/
│   ├── 荔枝/
│   └── ...
├── val/
└── test/

# 生成标注文件
python utils/generate_annotations.py --data-dir ./data
```

### 训练模型

```bash
# 基础训练
python training/train.py \
    --data ./data \
    --epochs 100 \
    --batch-size 32 \
    --lr 1e-3 \
    --img-size 224 \
    --save-dir ./checkpoints

# 知识蒸馏
python training/distill.py \
    --data ./data \
    --epochs 50 \
    --batch-size 32 \
    --lr 1e-4 \
    --save-dir ./checkpoints

# 模型剪枝
python training/prune.py \
    --model ./checkpoints/best_model.pth \
    --output ./checkpoints/pruned_model.pth \
    --target-size 50
```

### 模型评估

```bash
python inference/inference.py \
    --model ./checkpoints/best_model.pth \
    --backend pytorch \
    --benchmark
```

## 无人机套件部署

### 硬件清单

- [ ] 植保无人机（大疆T30/T40）
- [ ] 多光谱相机（MicaSense RedEdge-P）
- [ ] 变量喷头系统（定制）
- [ ] 边缘计算盒（Jetson Nano + 外壳）
- [ ] 4G/5G通信模块
- [ ] GPS/RTK定位模块

### 软件配置

```bash
# 安装MAVLink
cd drone-kit
pip install pymavlink dronekit

# 配置无人机参数
python configure_drone.py --port /dev/ttyUSB0 --baud 57600

# 测试连接
python test_connection.py
```

## 监控与维护

### 日志管理

```bash
# 查看后端日志
docker-compose logs -f backend | grep ERROR

# 查看边缘端日志
sudo journalctl -u zhinong-edge -f

# 日志轮转配置
sudo logrotate -f /etc/logrotate.d/zhinong
```

### 性能监控

```bash
# 系统资源
htop

# GPU监控 (Jetson)
tegrastats

# Docker资源
docker stats

# API性能
ab -n 1000 -c 10 http://localhost:8000/health
```

### 备份策略

```bash
# 数据库备份
pg_dump zhinong_db > backup_$(date +%Y%m%d).sql

# 模型备份
aws s3 sync ./checkpoints s3://zhinong-backup/models/

# 数据集备份
aws s3 sync ./data s3://zhinong-backup/datasets/
```

## 故障排查

### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 前端无法连接后端 | CORS配置错误 | 检查 `main.py` 中的CORS设置 |
| 数据库连接失败 | 网络/凭证错误 | 检查 `DATABASE_URL` 环境变量 |
| 模型推理超时 | GPU内存不足 | 减小batch_size或降低图像分辨率 |
| 边缘端推理慢 | 未启用TensorRT | 执行 `optimize.py` 生成TensorRT引擎 |
| 无人机无法连接 | 串口权限 | 添加用户到 `dialout` 组 |

### 诊断命令

```bash
# 网络连通性
curl -v http://localhost:8000/health

# 数据库连接
psql postgresql://zhinong:zhinong123@localhost:5432/zhinong_db -c "SELECT 1"

# Redis连接
redis-cli ping

# 模型加载测试
python -c "from inference.inference import InferenceEngine; e=InferenceEngine('model.onnx','onnx')"
```

## 安全加固

### HTTPS配置

```bash
# 使用 Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d zhinong.yourdomain.com
```

### 防火墙配置

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp  # 开发环境
sudo ufw enable
```

### 环境变量

创建 `.env` 文件：
```bash
# 数据库
DATABASE_URL=postgresql://zhinong:secure_password@localhost:5432/zhinong_db

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your-256-bit-secret-key

# AWS (可选)
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
S3_BUCKET=zhinong-data
```

---

**部署完成！** 访问 https://zhinong.yourdomain.com 开始使用。