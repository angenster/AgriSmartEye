# 智农慧眼 - 热带作物病虫害数据集

## 数据集概述

**智农慧眼**数据集是国内首个专门针对热带作物的病虫害开源数据集，旨在解决现有公开数据集中热带高湿、高温环境下识别准确率低的问题。

## 数据集统计

| 指标 | 数值 |
|------|------|
| 覆盖作物种类 | 15种 |
| 覆盖病虫害种类 | 42种 |
| 总图像数量 | 12,580张 |
| 图像分辨率 | 1920×1080 / 3840×2160 |
| 标注格式 | COCO + 自定义JSON |
| 数据增强 | 支持在线增强 |

## 作物种类

1. 芒果 (Mango)
2. 荔枝 (Lychee)
3. 槟榔 (Areca)
4. 香蕉 (Banana)
5. 菠萝 (Pineapple)
6. 火龙果 (Dragon Fruit)
7. 木瓜 (Papaya)
8. 椰子 (Coconut)
9. 橡胶 (Rubber)
10. 胡椒 (Pepper)
11. 咖啡 (Coffee)
12. 茶叶 (Tea)
13. 甘蔗 (Sugarcane)
14. 木薯 (Cassava)
15. 剑麻 (Sisal)

## 病虫害分类

### 芒果 (6种)
- 炭疽病 (Anthracnose)
- 白粉病 (Powdery Mildew)
- 细菌性角斑病 (Bacterial Angular Spot)
- 介壳虫 (Scale Insect)
- 蓟马 (Thrips)
- 瘿螨 (Gall Mite)

### 荔枝 (5种)
- 霜疫霉病 (Downy Blight)
- 炭疽病 (Anthracnose)
- 荔枝蝽 (Lychee Stink Bug)
- 蒂蛀虫 (Fruit Borer)
- 瘿螨 (Eriophyid Mite)

### 槟榔 (5种)
- 黄化病 (Yellow Leaf Disease)
- 炭疽病 (Anthracnose)
- 细菌性条斑病 (Bacterial Stripe)
- 红脉穗螟 (Red Stripe Borer)
- 蚧壳虫 (Mealybug)

### 香蕉 (5种)
- 枯萎病 (Fusarium Wilt)
- 叶斑病 (Leaf Spot)
- 黑星病 (Black Sigatoka)
- 象甲 (Weevil)
- 蚜虫 (Aphid)

### 其他 (21种)
详见 `utils/dataset.py` 中的 `DISEASE_CLASSES` 定义。

## 数据收集

### 采集地点
- 海南省：儋州、乐东、三亚、东方、琼海
- 采集时间：2023年3月 - 2024年5月
- 采集设备：Sony A7R IV, DJI P4 Multispectral, 智能手机

### 环境条件
- 不同光照条件：强光、阴天、清晨、黄昏
- 不同天气：晴天、多云、雨后
- 不同生长阶段：幼苗期、生长期、成熟期、采收期

## 标注规范

### 图像级标注
```json
{
  "file_name": "mango/anthracnose/IMG_001.jpg",
  "crop": "芒果",
  "crop_id": 0,
  "disease": "炭疽病",
  "disease_id": 0,
  "severity": "中度",
  "severity_id": 1,
  "bbox": [120, 80, 280, 220],
  "area": 15000
}
```

### 严重程度分级
- **轻度**：病斑面积 < 5%
- **中度**：病斑面积 5% - 25%
- **重度**：病斑面积 > 25%

## 数据集划分

```
data/
├── train/          # 训练集 (80%)
├── val/            # 验证集 (10%)
├── test/           # 测试集 (10%)
└── annotations/
    ├── train.json
    ├── val.json
    └── test.json
```

## 数据增强策略

训练时采用以下在线增强：
- 随机水平/垂直翻转
- 随机旋转（±30°）
- 随机缩放（0.8-1.2倍）
- 随机亮度/对比度调整
- 高斯噪声 / ISO噪声
- 色彩抖动（Hue/Saturation/Value）

## 下载与使用

### 通过代码加载
```python
from utils.dataset import get_dataloader

train_loader = get_dataloader(
    root_dir="./data",
    split="train",
    batch_size=32,
    img_size=224,
    augment=True,
)
```

### 数据格式转换
```bash
python utils/convert_coco.py --input data/annotations --output data/coco
```

## 许可协议

本数据集采用 **CC BY-NC-SA 4.0** 协议发布：
- 允许非商业用途的自由使用
- 使用时需注明来源
- 衍生作品需采用相同协议

## 引用

如果您在研究中使用本数据集，请引用：

```bibtex
@dataset{zhinong2024,
  title={智农慧眼：热带作物病虫害开源数据集},
  author={智农慧眼团队},
  year={2024},
  publisher={海南大学}
}
```

## 更新日志

- **v1.0 (2024.06)**：初始发布，15种作物、42种病虫害、12,580张图像
- **v1.1 (计划)**：增加多光谱数据、热成像数据

---

**联系我们**：zhinong@example.com