"""
智农慧眼 - 轻量化CNN模型架构
基于MobileNetV3 + 自定义分类头，专为热带作物病虫害识别设计
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
from typing import List


class SEBlock(nn.Module):
    """Squeeze-and-Excitation注意力模块"""
    def __init__(self, channels: int, reduction: int = 4):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(channels, channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channels // reduction, channels, bias=False),
            nn.Hardsigmoid(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _, _ = x.size()
        y = self.avg_pool(x).view(b, c)
        y = self.fc(y).view(b, c, 1, 1)
        return x * y.expand_as(x)


class DepthwiseSeparableConv(nn.Module):
    """深度可分离卷积（轻量化核心）"""
    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        kernel_size: int = 3,
        stride: int = 1,
        padding: int = 1,
    ):
        super().__init__()
        self.depthwise = nn.Conv2d(
            in_ch, in_ch, kernel_size, stride, padding, groups=in_ch, bias=False
        )
        self.bn1 = nn.BatchNorm2d(in_ch)
        self.pointwise = nn.Conv2d(in_ch, out_ch, 1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_ch)
        self.act = nn.Hardswish(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.act(self.bn1(self.depthwise(x)))
        x = self.act(self.bn2(self.pointwise(x)))
        return x


class InvertedResidual(nn.Module):
    """MobileNetV3倒残差块"""
    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        expansion: int,
        stride: int,
        use_se: bool = True,
    ):
        super().__init__()
        self.use_residual = stride == 1 and in_ch == out_ch
        hidden_ch = in_ch * expansion

        layers = []
        # 扩展
        if expansion != 1:
            layers.extend([
                nn.Conv2d(in_ch, hidden_ch, 1, bias=False),
                nn.BatchNorm2d(hidden_ch),
                nn.Hardswish(inplace=True),
            ])

        # 深度可分离卷积
        layers.extend([
            nn.Conv2d(hidden_ch, hidden_ch, 3, stride, 1, groups=hidden_ch, bias=False),
            nn.BatchNorm2d(hidden_ch),
            nn.Hardswish(inplace=True),
        ])

        if use_se:
            layers.append(SEBlock(hidden_ch))

        # 投影
        layers.extend([
            nn.Conv2d(hidden_ch, out_ch, 1, bias=False),
            nn.BatchNorm2d(out_ch),
        ])

        self.conv = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.use_residual:
            return x + self.conv(x)
        return self.conv(x)


class TropicalPestNet(nn.Module):
    """
    智农慧眼轻量化CNN模型
    基于MobileNetV3-Small骨干 + 自定义分类头
    目标：模型大小 < 50MB，准确率 > 95%
    """
    def __init__(
        self,
        num_classes: int = 42,
        num_crops: int = 15,
        pretrained: bool = True,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.num_classes = num_classes
        self.num_crops = num_crops

        # 加载预训练骨干网络
        weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
        backbone = mobilenet_v3_small(weights=weights)

        # 提取特征提取层（去掉最后的分类层）
        self.features = backbone.features
        self.avgpool = nn.AdaptiveAvgPool2d(1)

        # 计算特征维度
        with torch.no_grad():
            dummy = torch.zeros(1, 3, 224, 224)
            feat = self.features(dummy)
            feat_dim = feat.shape[1]

        # 多任务分类头
        # 任务1：作物种类识别
        self.crop_classifier = nn.Sequential(
            nn.Linear(feat_dim, 256),
            nn.Hardswish(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, num_crops),
        )

        # 任务2：病虫害识别
        self.disease_classifier = nn.Sequential(
            nn.Linear(feat_dim, 512),
            nn.Hardswish(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(512, num_classes),
        )

        # 任务3：严重程度评估
        self.severity_classifier = nn.Sequential(
            nn.Linear(feat_dim, 128),
            nn.Hardswish(inplace=True),
            nn.Dropout(dropout / 2),
            nn.Linear(128, 3),  # 轻/中/重
        )

        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> dict:
        # 特征提取
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)

        # 多任务输出
        return {
            "crop": self.crop_classifier(x),
            "disease": self.disease_classifier(x),
            "severity": self.severity_classifier(x),
            "features": x,
        }

    def get_model_size(self) -> dict:
        """获取模型大小统计"""
        param_size = sum(p.numel() for p in self.parameters()) * 4 / 1024 / 1024
        buffer_size = sum(b.numel() for b in self.buffers()) * 4 / 1024 / 1024
        total_size = param_size + buffer_size

        return {
            "param_size_mb": round(param_size, 2),
            "buffer_size_mb": round(buffer_size, 2),
            "total_size_mb": round(total_size, 2),
            "total_params": sum(p.numel() for p in self.parameters()),
            "trainable_params": sum(p.numel() for p in self.parameters() if p.requires_grad),
        }


def test_model():
    """测试模型"""
    model = TropicalPestNet(num_classes=42, num_crops=15)
    x = torch.randn(2, 3, 224, 224)
    outputs = model(x)

    print("=" * 60)
    print("智农慧眼 - TropicalPestNet 模型测试")
    print("=" * 60)
    print(f"输入形状: {x.shape}")
    print(f"作物输出: {outputs['crop'].shape} (15种作物)")
    print(f"病虫害输出: {outputs['disease'].shape} (42种病虫害)")
    print(f"严重程度输出: {outputs['severity'].shape} (3个等级)")
    print(f"特征维度: {outputs['features'].shape}")
    print("-" * 60)

    size_info = model.get_model_size()
    print(f"参数总量: {size_info['total_params']:,}")
    print(f"可训练参数: {size_info['trainable_params']:,}")
    print(f"模型大小: {size_info['total_size_mb']} MB")
    print("=" * 60)

    # 计算FLOPs
    try:
        from thop import profile
        flops, params = profile(model, inputs=(x,))
        print(f"FLOPs: {flops / 1e9:.2f} G")
        print(f"Params: {params / 1e6:.2f} M")
    except ImportError:
        print("未安装thop，跳过FLOPs计算")


if __name__ == "__main__":
    test_model()
