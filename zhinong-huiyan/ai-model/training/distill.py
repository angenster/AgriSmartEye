"""
智农慧眼 - 知识蒸馏训练
使用大型教师模型（ResNet50/EfficientNet-B3）指导轻量学生模型（MobileNetV3-Small）
蒸馏策略：软标签蒸馏 + 特征蒸馏 + 关系蒸馏
"""
import os
import sys
import argparse
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.cuda.amp import autocast, GradScaler
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.lightweight_cnn import TropicalPestNet
from utils.dataset import get_dataloader, DISEASE_CLASSES, CROP_CLASSES
from torchvision.models import resnet50, ResNet50_Weights


class DistillationLoss(nn.Module):
    """知识蒸馏损失"""
    def __init__(
        self,
        temperature: float = 4.0,
        alpha: float = 0.7,
        beta: float = 0.2,
        gamma: float = 0.1,
    ):
        super().__init__()
        self.temperature = temperature
        self.alpha = alpha  # 软标签权重
        self.beta = beta    # 硬标签权重
        self.gamma = gamma  # 特征蒸馏权重
        self.ce_loss = nn.CrossEntropyLoss()
        self.kl_loss = nn.KLDivLoss(reduction="batchmean")

    def forward(
        self,
        student_outputs: dict,
        teacher_outputs: dict,
        labels: dict,
    ) -> torch.Tensor:
        # 硬标签损失
        loss_hard = (
            self.ce_loss(student_outputs["disease"], labels["disease_id"]) +
            self.ce_loss(student_outputs["crop"], labels["crop_id"]) +
            self.ce_loss(student_outputs["severity"], labels["severity_id"])
        )

        # 软标签损失 (KL散度)
        T = self.temperature
        loss_soft = (
            self.kl_loss(
                F.log_softmax(student_outputs["disease"] / T, dim=1),
                F.softmax(teacher_outputs["disease"] / T, dim=1),
            ) * (T * T) +
            self.kl_loss(
                F.log_softmax(student_outputs["crop"] / T, dim=1),
                F.softmax(teacher_outputs["crop"] / T, dim=1),
            ) * (T * T)
        )

        # 特征蒸馏损失 (MSE)
        loss_feat = F.mse_loss(student_outputs["features"], teacher_outputs["features"])

        return self.alpha * loss_soft + self.beta * loss_hard + self.gamma * loss_feat


class TeacherModel(nn.Module):
    """教师模型：ResNet50"""
    def __init__(self, num_classes: int = 42, num_crops: int = 15):
        super().__init__()
        backbone = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)
        feat_dim = backbone.fc.in_features

        self.features = nn.Sequential(*list(backbone.children())[:-1])
        self.crop_head = nn.Linear(feat_dim, num_crops)
        self.disease_head = nn.Linear(feat_dim, num_classes)
        self.severity_head = nn.Linear(feat_dim, 3)

    def forward(self, x):
        feat = self.features(x)
        feat = torch.flatten(feat, 1)
        return {
            "crop": self.crop_head(feat),
            "disease": self.disease_head(feat),
            "severity": self.severity_head(feat),
            "features": feat,
        }


def train_with_distillation(
    teacher: nn.Module,
    student: nn.Module,
    train_loader,
    val_loader,
    epochs: int = 50,
    lr: float = 1e-4,
    device: str = "cuda",
    save_dir: str = "../checkpoints",
):
    """蒸馏训练"""
    teacher = teacher.to(device).eval()
    student = student.to(device).train()

    # 冻结教师模型
    for param in teacher.parameters():
        param.requires_grad = False

    criterion = DistillationLoss(temperature=4.0, alpha=0.7)
    optimizer = optim.AdamW(student.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    scaler = GradScaler()

    best_acc = 0

    for epoch in range(epochs):
        student.train()
        total_loss = 0

        pbar = tqdm(train_loader, desc=f"Distill Epoch {epoch+1}")
        for images, labels in pbar:
            images = images.to(device)
            crop_ids = labels["crop_id"].to(device)
            disease_ids = labels["disease_id"].to(device)
            severity_ids = labels["severity_id"].to(device)
            label_dict = {"crop_id": crop_ids, "disease_id": disease_ids, "severity_id": severity_ids}

            optimizer.zero_grad()

            with autocast():
                with torch.no_grad():
                    teacher_out = teacher(images)
                student_out = student(images)
                loss = criterion(student_out, teacher_out, label_dict)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            total_loss += loss.item()
            pbar.set_postfix({"loss": f"{loss.item():.4f}"})

        scheduler.step()

        # 验证
        student.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                disease_ids = labels["disease_id"].to(device)
                outputs = student(images)
                _, predicted = outputs["disease"].max(1)
                correct += (predicted == disease_ids).sum().item()
                total += disease_ids.size(0)

        acc = correct / total * 100
        print(f"Epoch {epoch+1}: Loss={total_loss/len(train_loader):.4f}, Val Acc={acc:.2f}%")

        if acc > best_acc:
            best_acc = acc
            torch.save(student.state_dict(), os.path.join(save_dir, "distilled_model.pth"))
            print(f"✓ 保存最佳蒸馏模型 (Acc: {best_acc:.2f}%)")

    print(f"蒸馏完成！最佳准确率: {best_acc:.2f}%")
    return student


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="../data")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--save-dir", default="../checkpoints")
    args = parser.parse_args()

    os.makedirs(args.save_dir, exist_ok=True)

    print("加载教师模型 (ResNet50)...")
    teacher = TeacherModel(len(DISEASE_CLASSES), len(CROP_CLASSES))

    print("加载学生模型 (MobileNetV3-Small)...")
    student = TropicalPestNet(len(DISEASE_CLASSES), len(CROP_CLASSES), pretrained=True)

    print("加载数据集...")
    train_loader = get_dataloader(args.data, "train", args.batch_size, num_workers=4)
    val_loader = get_dataloader(args.data, "val", args.batch_size, num_workers=4)

    print("开始知识蒸馏...")
    train_with_distillation(
        teacher, student, train_loader, val_loader,
        args.epochs, args.lr, args.device, args.save_dir,
    )


if __name__ == "__main__":
    main()
