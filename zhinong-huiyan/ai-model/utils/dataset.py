"""
热带作物病虫害数据集加载器
支持数据增强、类别均衡、多尺度训练
"""
import os
import json
import random
from pathlib import Path
from typing import Tuple, List, Optional, Callable

import torch
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torchvision import transforms
from PIL import Image
import numpy as np
import albumentations as A
from albumentations.pytorch import ToTensorV2


# 作物种类映射
CROP_CLASSES = [
    "芒果", "荔枝", "槟榔", "香蕉", "菠萝",
    "火龙果", "木瓜", "椰子", "橡胶", "胡椒",
    "咖啡", "茶叶", "甘蔗", "木薯", "剑麻",
]

# 病虫害种类映射
DISEASE_CLASSES = [
    # 芒果 (6种)
    "芒果炭疽病", "芒果白粉病", "芒果细菌性角斑病", "芒果介壳虫", "芒果蓟马", "芒果瘿螨",
    # 荔枝 (5种)
    "荔枝霜疫霉病", "荔枝炭疽病", "荔枝蝽", "荔枝蒂蛀虫", "荔枝瘿螨",
    # 槟榔 (5种)
    "槟榔黄化病", "槟榔炭疽病", "槟榔细菌性条斑病", "槟榔红脉穗螟", "槟榔蚧壳虫",
    # 香蕉 (5种)
    "香蕉枯萎病", "香蕉叶斑病", "香蕉黑星病", "香蕉象甲", "香蕉蚜虫",
    # 菠萝 (4种)
    "菠萝心腐病", "菠萝黑腐病", "菠萝粉蚧", "菠萝红蜘蛛",
    # 火龙果 (4种)
    "火龙果溃疡病", "火龙果炭疽病", "火龙果蜗牛", "火龙果介壳虫",
    # 木瓜 (4种)
    "木瓜花叶病", "木瓜炭疽病", "木瓜红蜘蛛", "木瓜介壳虫",
    # 其他 (9种)
    "椰子红环腐病", "橡胶白粉病", "胡椒瘟病", "咖啡锈病",
    "茶叶茶饼病", "甘蔗赤腐病", "木薯细菌性枯萎病", "剑斑马纹病",
    "健康",  # 无病虫害
]

# 严重程度
SEVERITY_CLASSES = ["轻度", "中度", "重度"]


class TropicalCropDataset(Dataset):
    """
    热带作物病虫害数据集
    支持：单标签分类、多任务学习、目标检测框标注
    """
    def __init__(
        self,
        root_dir: str,
        split: str = "train",
        img_size: int = 224,
        augment: bool = True,
        cache_images: bool = False,
    ):
        self.root_dir = Path(root_dir)
        self.split = split
        self.img_size = img_size
        self.augment = augment
        self.cache_images = cache_images
        self.image_cache = {}

        # 加载标注文件
        self.annotations = self._load_annotations()
        self.samples = self._build_samples()

        # 数据增强
        self.transform = self._build_transforms()

        print(f"[{split}] 加载完成: {len(self.samples)} 张图像")

    def _load_annotations(self) -> dict:
        """加载标注JSON文件"""
        anno_file = self.root_dir / f"annotations_{self.split}.json"
        if anno_file.exists():
            with open(anno_file, "r", encoding="utf-8") as f:
                return json.load(f)
        # 如果没有标注文件，尝试从目录结构推断
        return self._build_annotations_from_dir()

    def _build_annotations_from_dir(self) -> dict:
        """从目录结构构建标注（作物/病虫害/图像）"""
        annotations = {"images": []}
        img_dir = self.root_dir / self.split

        if not img_dir.exists():
            return annotations

        for crop_dir in img_dir.iterdir():
            if not crop_dir.is_dir():
                continue
            crop_name = crop_dir.name
            crop_idx = CROP_CLASSES.index(crop_name) if crop_name in CROP_CLASSES else -1

            for disease_dir in crop_dir.iterdir():
                if not disease_dir.is_dir():
                    continue
                disease_name = disease_dir.name
                disease_idx = DISEASE_CLASSES.index(disease_name) if disease_name in DISEASE_CLASSES else -1

                for img_file in disease_dir.glob("*.jpg"):
                    annotations["images"].append({
                        "file_name": str(img_file.relative_to(self.root_dir)),
                        "crop": crop_name,
                        "crop_id": crop_idx,
                        "disease": disease_name,
                        "disease_id": disease_idx,
                        "severity": random.choice(SEVERITY_CLASSES),
                        "severity_id": random.randint(0, 2),
                    })

        return annotations

    def _build_samples(self) -> List[dict]:
        """构建样本列表"""
        return self.annotations.get("images", [])

    def _build_transforms(self):
        """构建数据增强管道"""
        if self.augment and self.split == "train":
            return A.Compose([
                A.Resize(self.img_size, self.img_size),
                A.HorizontalFlip(p=0.5),
                A.VerticalFlip(p=0.3),
                A.RandomRotate90(p=0.5),
                A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.2, rotate_limit=30, p=0.5),
                A.OneOf([
                    A.RandomBrightnessContrast(p=1),
                    A.RandomGamma(p=1),
                ], p=0.5),
                A.OneOf([
                    A.GaussNoise(p=1),
                    A.ISONoise(p=1),
                ], p=0.3),
                A.Blur(blur_limit=3, p=0.2),
                A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=20, val_shift_limit=10, p=0.3),
                A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ToTensorV2(),
            ])
        else:
            return A.Compose([
                A.Resize(self.img_size, self.img_size),
                A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ToTensorV2(),
            ])

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, dict]:
        sample = self.samples[idx]
        img_path = self.root_dir / sample["file_name"]

        # 图像加载（支持缓存）
        if self.cache_images and str(img_path) in self.image_cache:
            image = self.image_cache[str(img_path)]
        else:
            image = np.array(Image.open(img_path).convert("RGB"))
            if self.cache_images:
                self.image_cache[str(img_path)] = image

        # 数据增强
        transformed = self.transform(image=image)
        image_tensor = transformed["image"]

        # 标签
        labels = {
            "crop_id": torch.tensor(sample.get("crop_id", 0), dtype=torch.long),
            "disease_id": torch.tensor(sample.get("disease_id", 0), dtype=torch.long),
            "severity_id": torch.tensor(sample.get("severity_id", 0), dtype=torch.long),
        }

        return image_tensor, labels


def get_dataloader(
    root_dir: str,
    split: str = "train",
    batch_size: int = 32,
    img_size: int = 224,
    num_workers: int = 4,
    balance: bool = True,
) -> DataLoader:
    """创建数据加载器"""
    dataset = TropicalCropDataset(
        root_dir=root_dir,
        split=split,
        img_size=img_size,
        augment=(split == "train"),
    )

    sampler = None
    if balance and split == "train":
        # 类别均衡采样
        disease_ids = [s.get("disease_id", 0) for s in dataset.samples]
        class_counts = np.bincount(disease_ids)
        class_weights = 1.0 / class_counts
        sample_weights = [class_weights[did] for did in disease_ids]
        sampler = WeightedRandomSampler(sample_weights, len(sample_weights))

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=(sampler is None and split == "train"),
        sampler=sampler,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=(split == "train"),
    )


if __name__ == "__main__":
    # 测试数据集
    print("测试数据集加载器...")
    print(f"作物种类: {len(CROP_CLASSES)} 种")
    print(f"病虫害种类: {len(DISEASE_CLASSES)} 种")
    print(f"严重程度: {len(SEVERITY_CLASSES)} 级")
