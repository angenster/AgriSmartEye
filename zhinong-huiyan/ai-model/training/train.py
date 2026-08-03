"""
智农慧眼 - 模型训练脚本
支持：多任务训练、混合精度、学习率调度、早停、模型检查点
"""
import os
import sys
import argparse
import time
from pathlib import Path
from typing import Dict

import torch
import torch.nn as nn
import torch.optim as optim
from torch.cuda.amp import autocast, GradScaler
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
import numpy as np

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.lightweight_cnn import TropicalPestNet
from utils.dataset import get_dataloader, CROP_CLASSES, DISEASE_CLASSES, SEVERITY_CLASSES


def parse_args():
    parser = argparse.ArgumentParser(description="训练智农慧眼模型")
    parser.add_argument("--data", type=str, default="../data", help="数据集路径")
    parser.add_argument("--epochs", type=int, default=100, help="训练轮数")
    parser.add_argument("--batch-size", type=int, default=32, help="批次大小")
    parser.add_argument("--lr", type=float, default=1e-3, help="初始学习率")
    parser.add_argument("--img-size", type=int, default=224, help="图像尺寸")
    parser.add_argument("--device", type=str, default="cuda", help="训练设备")
    parser.add_argument("--workers", type=int, default=4, help="数据加载线程数")
    parser.add_argument("--save-dir", type=str, default="../checkpoints", help="模型保存路径")
    parser.add_argument("--pretrained", action="store_true", default=True, help="使用预训练权重")
    parser.add_argument("--amp", action="store_true", default=True, help="混合精度训练")
    parser.add_argument("--resume", type=str, default="", help="恢复训练的检查点")
    return parser.parse_args()


class MultiTaskLoss(nn.Module):
    """多任务损失函数（自适应权重）"""
    def __init__(self):
        super().__init__()
        self.log_vars = nn.Parameter(torch.zeros(3))  # 3个任务的噪声参数

    def forward(self, losses: Dict[str, torch.Tensor]) -> torch.Tensor:
        total_loss = 0
        for i, (name, loss) in enumerate(losses.items()):
            precision = torch.exp(-self.log_vars[i])
            total_loss += precision * loss + self.log_vars[i]
        return total_loss


def train_epoch(
    model: nn.Module,
    dataloader,
    optimizer,
    criterion,
    multitask_loss,
    scaler,
    device,
    use_amp,
    epoch,
):
    """单轮训练"""
    model.train()
    total_loss = 0
    total_crop_acc = 0
    total_disease_acc = 0
    total_severity_acc = 0
    num_batches = len(dataloader)

    pbar = tqdm(dataloader, desc=f"Epoch {epoch}")
    for images, labels in pbar:
        images = images.to(device, non_blocking=True)
        crop_ids = labels["crop_id"].to(device, non_blocking=True)
        disease_ids = labels["disease_id"].to(device, non_blocking=True)
        severity_ids = labels["severity_id"].to(device, non_blocking=True)

        optimizer.zero_grad()

        with autocast(enabled=use_amp):
            outputs = model(images)
            loss_crop = criterion(outputs["crop"], crop_ids)
            loss_disease = criterion(outputs["disease"], disease_ids)
            loss_severity = criterion(outputs["severity"], severity_ids)

            losses = {
                "crop": loss_crop,
                "disease": loss_disease,
                "severity": loss_severity,
            }
            loss = multitask_loss(losses)

        if use_amp:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            optimizer.step()

        # 统计
        total_loss += loss.item()
        total_crop_acc += (outputs["crop"].argmax(1) == crop_ids).float().mean().item()
        total_disease_acc += (outputs["disease"].argmax(1) == disease_ids).float().mean().item()
        total_severity_acc += (outputs["severity"].argmax(1) == severity_ids).float().mean().item()

        pbar.set_postfix({
            "loss": f"{loss.item():.4f}",
            "crop": f"{total_crop_acc/(pbar.n+1)*100:.1f}%",
            "disease": f"{total_disease_acc/(pbar.n+1)*100:.1f}%",
        })

    return {
        "loss": total_loss / num_batches,
        "crop_acc": total_crop_acc / num_batches * 100,
        "disease_acc": total_disease_acc / num_batches * 100,
        "severity_acc": total_severity_acc / num_batches * 100,
    }


@torch.no_grad()
def validate(model: nn.Module, dataloader, criterion, device):
    """验证"""
    model.eval()
    total_loss = 0
    total_crop_acc = 0
    total_disease_acc = 0
    total_severity_acc = 0
    num_batches = len(dataloader)

    for images, labels in tqdm(dataloader, desc="Validating"):
        images = images.to(device, non_blocking=True)
        crop_ids = labels["crop_id"].to(device, non_blocking=True)
        disease_ids = labels["disease_id"].to(device, non_blocking=True)
        severity_ids = labels["severity_id"].to(device, non_blocking=True)

        outputs = model(images)
        loss_crop = criterion(outputs["crop"], crop_ids)
        loss_disease = criterion(outputs["disease"], disease_ids)
        loss_severity = criterion(outputs["severity"], severity_ids)
        loss = loss_crop + loss_disease + loss_severity

        total_loss += loss.item()
        total_crop_acc += (outputs["crop"].argmax(1) == crop_ids).float().mean().item()
        total_disease_acc += (outputs["disease"].argmax(1) == disease_ids).float().mean().item()
        total_severity_acc += (outputs["severity"].argmax(1) == severity_ids).float().mean().item()

    return {
        "loss": total_loss / num_batches,
        "crop_acc": total_crop_acc / num_batches * 100,
        "disease_acc": total_disease_acc / num_batches * 100,
        "severity_acc": total_severity_acc / num_batches * 100,
    }


def main():
    args = parse_args()
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")

    # 创建保存目录
    os.makedirs(args.save_dir, exist_ok=True)

    # 数据加载
    print("加载数据集...")
    train_loader = get_dataloader(
        args.data, "train", args.batch_size, args.img_size, args.workers, balance=True
    )
    val_loader = get_dataloader(
        args.data, "val", args.batch_size, args.img_size, args.workers, balance=False
    )

    # 模型
    print("初始化模型...")
    model = TropicalPestNet(
        num_classes=len(DISEASE_CLASSES),
        num_crops=len(CROP_CLASSES),
        pretrained=args.pretrained,
    )
    print(model.get_model_size())
    model = model.to(device)

    # 损失与优化器
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    multitask_loss = MultiTaskLoss().to(device)
    optimizer = optim.AdamW(
        list(model.parameters()) + list(multitask_loss.parameters()),
        lr=args.lr,
        weight_decay=1e-4,
    )
    scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=10, T_mult=2
    )
    scaler = GradScaler() if args.amp else None

    # TensorBoard
    writer = SummaryWriter(log_dir=os.path.join(args.save_dir, "logs"))

    # 训练循环
    best_acc = 0
    start_epoch = 0

    for epoch in range(start_epoch, args.epochs):
        print(f"\n{'='*60}")
        print(f"Epoch {epoch+1}/{args.epochs}")
        print(f"{'='*60}")

        train_metrics = train_epoch(
            model, train_loader, optimizer, criterion,
            multitask_loss, scaler, device, args.amp, epoch+1
        )

        val_metrics = validate(model, val_loader, criterion, device)
        scheduler.step()

        # 日志
        print(f"\n训练 - Loss: {train_metrics['loss']:.4f}, "
              f"作物: {train_metrics['crop_acc']:.2f}%, "
              f"病害: {train_metrics['disease_acc']:.2f}%, "
              f"严重: {train_metrics['severity_acc']:.2f}%")
        print(f"验证 - Loss: {val_metrics['loss']:.4f}, "
              f"作物: {val_metrics['crop_acc']:.2f}%, "
              f"病害: {val_metrics['disease_acc']:.2f}%, "
              f"严重: {val_metrics['severity_acc']:.2f}%")

        writer.add_scalars("Loss", {"train": train_metrics["loss"], "val": val_metrics["loss"]}, epoch)
        writer.add_scalars("Disease_Acc", {"train": train_metrics["disease_acc"], "val": val_metrics["disease_acc"]}, epoch)

        # 保存最佳模型
        avg_acc = (val_metrics["disease_acc"] + val_metrics["crop_acc"]) / 2
        if avg_acc > best_acc:
            best_acc = avg_acc
            torch.save({
                "epoch": epoch,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "best_acc": best_acc,
            }, os.path.join(args.save_dir, "best_model.pth"))
            print(f"✓ 保存最佳模型 (Acc: {best_acc:.2f}%)")

        # 定期保存
        if (epoch + 1) % 10 == 0:
            torch.save({
                "epoch": epoch,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
            }, os.path.join(args.save_dir, f"checkpoint_epoch_{epoch+1}.pth"))

    writer.close()
    print(f"\n训练完成！最佳准确率: {best_acc:.2f}%")


if __name__ == "__main__":
    main()
