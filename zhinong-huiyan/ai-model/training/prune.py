"""
智农慧眼 - 模型结构化剪枝
通道剪枝 + 层剪枝，保持模型结构的同时大幅压缩参数量
目标：模型大小 < 50MB，推理延迟 < 100ms
"""
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List

import torch
import torch.nn as nn
import torch.nn.utils.prune as prune
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.lightweight_cnn import TropicalPestNet


def get_channel_importance(conv_layer: nn.Conv2d) -> torch.Tensor:
    """计算卷积层各通道的重要性（L1范数）"""
    weights = conv_layer.weight.data.abs()
    importance = weights.sum(dim=[1, 2, 3])  # 每个输出通道的重要性
    return importance


def prune_conv_layer(conv: nn.Conv2d, bn: nn.BatchNorm2d, prune_ratio: float):
    """对卷积层及其BN层进行通道剪枝"""
    importance = get_channel_importance(conv)
    num_channels = conv.out_channels
    num_keep = int(num_channels * (1 - prune_ratio))

    _, keep_indices = torch.topk(importance, num_keep)
    keep_indices = keep_indices.sort()[0]

    # 剪枝卷积层
    conv.out_channels = num_keep
    conv.weight = nn.Parameter(conv.weight.data[keep_indices])
    if conv.bias is not None:
        conv.bias = nn.Parameter(conv.bias.data[keep_indices])

    # 剪枝BN层
    bn.num_features = num_keep
    bn.weight = nn.Parameter(bn.weight.data[keep_indices])
    bn.bias = nn.Parameter(bn.bias.data[keep_indices])
    bn.running_mean = bn.running_mean[keep_indices]
    bn.running_var = bn.running_var[keep_indices]

    return keep_indices


def prune_model(model: nn.Module, prune_ratio: float = 0.3) -> nn.Module:
    """对整个模型进行结构化剪枝"""
    model = deepcopy(model)
    pruned_layers = 0

    for name, module in list(model.named_modules()):
        if isinstance(module, nn.Conv2d) and module.out_channels > 16:
            # 找到对应的BN层
            parent_name = ".".join(name.split(".")[:-1])
            child_name = name.split(".")[-1]

            try:
                parent = model
                for part in parent_name.split("."):
                    if part:
                        parent = getattr(parent, part)

                # 尝试找到对应的BN层（通常紧跟在Conv之后）
                bn_name = None
                children = list(parent.named_children())
                for i, (cname, _) in enumerate(children):
                    if cname == child_name and i + 1 < len(children):
                        next_name, next_module = children[i + 1]
                        if isinstance(next_module, nn.BatchNorm2d):
                            bn_name = next_name
                            break

                if bn_name:
                    keep_indices = prune_conv_layer(module, getattr(parent, bn_name), prune_ratio)

                    # 调整下一层的输入通道
                    if i + 2 < len(children):
                        next_next_name, next_next_module = children[i + 2]
                        if isinstance(next_next_module, nn.Conv2d):
                            next_next_module.in_channels = len(keep_indices)
                            next_next_module.weight = nn.Parameter(
                                next_next_module.weight.data[:, keep_indices]
                            )

                    pruned_layers += 1
            except Exception as e:
                print(f"跳过层 {name}: {e}")

    print(f"剪枝完成: {pruned_layers} 层被剪枝，剪枝比例: {prune_ratio*100:.1f}%")
    return model


def measure_model(model: nn.Module, input_size: tuple = (1, 3, 224, 224)):
    """测量模型参数和计算量"""
    model.eval()
    dummy_input = torch.randn(input_size)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    # 估计模型大小
    param_size_mb = total_params * 4 / 1024 / 1024

    # 计算FLOPs
    try:
        from thop import profile
        flops, params = profile(model, inputs=(dummy_input,), verbose=False)
        flops_g = flops / 1e9
    except ImportError:
        flops_g = 0
        params = total_params

    return {
        "total_params": total_params,
        "trainable_params": trainable_params,
        "param_size_mb": round(param_size_mb, 2),
        "flops_g": round(flops_g, 2),
    }


def iterative_prune(
    model: nn.Module,
    target_size_mb: float = 50,
    target_acc_drop: float = 2.0,
    val_loader=None,
):
    """迭代剪枝直到达到目标大小"""
    original_metrics = measure_model(model)
    print(f"原始模型: {original_metrics}")

    current_ratio = 0.1
    best_model = model

    while current_ratio <= 0.7:
        print(f"\n尝试剪枝比例: {current_ratio*100:.0f}%")
        pruned_model = prune_model(deepcopy(model), current_ratio)
        metrics = measure_model(pruned_model)

        print(f"剪枝后: {metrics}")

        if metrics["param_size_mb"] <= target_size_mb:
            best_model = pruned_model
            print(f"✓ 达到目标大小 ({target_size_mb}MB)")
            break

        current_ratio += 0.1

    final_metrics = measure_model(best_model)
    print(f"\n最终模型: {final_metrics}")
    print(f"压缩率: {(1 - final_metrics['total_params'] / original_metrics['total_params']) * 100:.1f}%")

    return best_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True, help="输入模型路径")
    parser.add_argument("--output", type=str, default="../checkpoints/pruned_model.pth", help="输出路径")
    parser.add_argument("--target-size", type=float, default=50, help="目标模型大小(MB)")
    parser.add_argument("--prune-ratio", type=float, default=0.3, help="剪枝比例")
    args = parser.parse_args()

    print("加载模型...")
    checkpoint = torch.load(args.model, map_location="cpu")
    model = TropicalPestNet()
    model.load_state_dict(checkpoint.get("model", checkpoint))

    print("开始剪枝...")
    if args.prune_ratio > 0:
        pruned_model = prune_model(model, args.prune_ratio)
    else:
        pruned_model = iterative_prune(model, args.target_size)

    # 保存
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    torch.save(pruned_model.state_dict(), args.output)
    print(f"剪枝模型已保存: {args.output}")


if __name__ == "__main__":
    main()
