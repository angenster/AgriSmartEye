# 智农慧眼 API 文档

## 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **协议**: HTTP/HTTPS
- **数据格式**: JSON
- **认证方式**: Bearer Token (JWT)

## 认证

### 用户注册
```http
POST /auth/register
Content-Type: application/json

{
  "username": "farmer01",
  "email": "farmer@example.com",
  "password": "password123",
  "full_name": "张三",
  "organization": "儋州芒果合作社"
}
```

### 用户登录
```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=farmer01&password=password123
```

响应：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### 获取当前用户
```http
GET /auth/me
Authorization: Bearer <token>
```

## 病虫害识别

### 上传图像识别
```http
POST /detection/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <图像文件>
crop_type: "芒果"
confidence_threshold: 0.85
```

响应：
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "crop_type": "芒果",
      "disease_name": "炭疽病",
      "confidence": 97.8,
      "severity": "中度",
      "bbox": [120, 80, 280, 220],
      "recommendation": "及时喷洒咪鲜胺或苯醚甲环唑...",
      "medicine": "45%咪鲜胺水乳剂",
      "dosage": "稀释1500-2000倍液",
      "inference_time": 156.2,
      "model_version": "v1.0",
      "created_at": "2024-06-01T09:23:15"
    }
  ],
  "message": "成功识别 1 处病虫害，推理耗时 156.2ms"
}
```

### Base64图像识别
```http
POST /detection/base64
Authorization: Bearer <token>
Content-Type: application/json

{
  "image_base64": "/9j/4AAQSkZJRgABAQAAAQ...",
  "crop_type": "芒果",
  "confidence_threshold": 0.85
}
```

### 获取识别历史
```http
GET /detection/history?limit=50
Authorization: Bearer <token>
```

### 识别统计
```http
GET /detection/stats
Authorization: Bearer <token>
```

响应：
```json
{
  "total_detections": 1284,
  "today_count": 23,
  "avg_confidence": 97.5,
  "model_version": "v1.0"
}
```

## 田块管理

### 创建田块
```http
POST /fields/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "A区03号田",
  "crop_type": "芒果",
  "area": 15.6,
  "location": "儋州市那大镇",
  "latitude": 19.5167,
  "longitude": 109.5833
}
```

### 获取田块列表
```http
GET /fields/?skip=0&limit=100
Authorization: Bearer <token>
```

### 获取田块详情
```http
GET /fields/{field_id}
Authorization: Bearer <token>
```

### 更新田块
```http
PUT /fields/{field_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "moderate",
  "next_spray": "2024-06-03T08:00:00"
}
```

### 删除田块
```http
DELETE /fields/{field_id}
Authorization: Bearer <token>
```

### 添加操作记录
```http
POST /fields/{field_id}/operations
Authorization: Bearer <token>
Content-Type: application/json

{
  "type": "ai_inspection",
  "content": "发现炭疽病中度感染",
  "operator": "系统"
}
```

### 获取操作记录
```http
GET /fields/{field_id}/operations
Authorization: Bearer <token>
```

## 无人机控制

### 获取无人机列表
```http
GET /drone/
Authorization: Bearer <token>
```

### 获取无人机状态
```http
GET /drone/{drone_id}
Authorization: Bearer <token>
```

### 发送控制指令
```http
POST /drone/{drone_id}/command
Authorization: Bearer <token>
Content-Type: application/json

{
  "command": "start",
  "variable_spray": true
}
```

指令类型：`start` | `pause` | `return` | `emergency`

### 获取任务状态
```http
GET /drone/{drone_id}/mission
Authorization: Bearer <token>
```

## 数据分析

### 数据摘要
```http
GET /analysis/summary
Authorization: Bearer <token>
```

响应：
```json
{
  "total_detections": 1284,
  "total_fields": 8,
  "total_sprayed_area": 385.6,
  "total_medicine_saved": 2456.3,
  "avg_confidence": 97.5,
  "monthly_stats": [
    {
      "month": "2024-01",
      "detections": 120,
      "sprayed_area": 45.2
    }
  ]
}
```

### 成本对比
```http
GET /analysis/cost-comparison
Authorization: Bearer <token>
```

### 施药记录
```http
GET /analysis/spray-records?limit=50
Authorization: Bearer <token>
```

### 病虫害分布
```http
GET /analysis/disease-distribution
Authorization: Bearer <token>
```

## 知识库

### 获取病虫害列表
```http
GET /knowledge/?crop_type=芒果&search=炭疽&limit=20
```

### 获取病虫害详情
```http
GET /knowledge/{pest_id}
```

### 获取作物类型
```http
GET /knowledge/crops/types
```

### 知识库统计
```http
GET /knowledge/stats/overview
```

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 422 | 验证错误 |
| 500 | 服务器内部错误 |

## 限流策略

- 认证接口：10次/分钟
- 识别接口：30次/分钟
- 其他接口：100次/分钟

## SDK示例

### Python
```python
import requests

API_BASE = "http://localhost:8000/api/v1"
token = "your_jwt_token"
headers = {"Authorization": f"Bearer {token}"}

# 上传识别
with open("mango.jpg", "rb") as f:
    response = requests.post(
        f"{API_BASE}/detection/upload",
        headers=headers,
        files={"file": f},
        data={"crop_type": "芒果"}
    )
    print(response.json())
```

### JavaScript
```javascript
const API_BASE = 'http://localhost:8000/api/v1';

async function detectPest(imageFile, token) {
  const formData = new FormData();
  formData.append('file', imageFile);
  formData.append('crop_type', '芒果');

  const response = await fetch(`${API_BASE}/detection/upload`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData,
  });

  return await response.json();
}
```