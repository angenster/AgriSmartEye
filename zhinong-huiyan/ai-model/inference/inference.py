"""
智农慧眼 - 推理引擎
支持：PyTorch、ONNX、TensorRT多后端推理
目标：边缘端实时推理 (< 200ms@Jetson Nano)
"""
import os
import time
from pathlib import Path
from typing import Union, List, Dict, Tuple

import torch
import torch.nn as nn
import numpy as np
from PIL import Image
import torchvision.transforms as T

# 可选后端
try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False

try:
    import tensorrt as trt
    HAS_TRT = True
except ImportError:
    HAS_TRT = False


class InferenceEngine:
    """智农慧眼推理引擎"""

    def __init__(
        self,
        model_path: str,
        backend: str = "pytorch",
        device: str = "cuda",
        img_size: int = 224,
        num_classes: int = 42,
        num_crops: int = 15,
    ):
        self.backend = backend.lower()
        self.device = device
        self.img_size = img_size
        self.num_classes = num_classes
        self.num_crops = num_crops

        # 预处理
        self.transform = T.Compose([
            T.Resize((img_size, img_size)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        # 加载模型
        if self.backend == "pytorch":
            self._load_pytorch(model_path)
        elif self.backend == "onnx":
            self._load_onnx(model_path)
        elif self.backend == "tensorrt":
            self._load_tensorrt(model_path)
        else:
            raise ValueError(f"不支持的后端: {backend}")

        print(f"推理引擎初始化完成: backend={backend}, device={device}")

    def _load_pytorch(self, model_path: str):
        """加载PyTorch模型"""
        sys_path = str(Path(__file__).parent.parent)
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)

        from models.lightweight_cnn import TropicalPestNet
        self.model = TropicalPestNet(self.num_classes, self.num_crops)

        checkpoint = torch.load(model_path, map_location=self.device)
        state_dict = checkpoint.get("model", checkpoint)
        self.model.load_state_dict(state_dict)
        self.model = self.model.to(self.device).eval()

        # 计算模型大小
        size_info = self.model.get_model_size()
        print(f"模型大小: {size_info['total_size_mb']} MB")

    def _load_onnx(self, model_path: str):
        """加载ONNX模型"""
        if not HAS_ONNX:
            raise ImportError("请先安装 onnxruntime: pip install onnxruntime")

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        print("ONNX模型加载完成")

    def _load_tensorrt(self, engine_path: str):
        """加载TensorRT引擎"""
        if not HAS_TRT:
            raise ImportError("TensorRT未安装")

        logger = trt.Logger(trt.Logger.WARNING)
        with open(engine_path, "rb") as f:
            runtime = trt.Runtime(logger)
            self.engine = runtime.deserialize_cuda_engine(f.read())

        self.context = self.engine.create_execution_context()
        print("TensorRT引擎加载完成")

    def preprocess(self, image: Union[str, np.ndarray, Image.Image]) -> torch.Tensor:
        """图像预处理"""
        if isinstance(image, str):
            image = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            image = Image.fromarray(image)

        return self.transform(image).unsqueeze(0)

    @torch.no_grad()
    def predict(self, image: Union[str, np.ndarray, Image.Image]) -> Dict:
        """
        单张图像推理
        返回: {
            "crop": {"name": str, "confidence": float},
            "disease": {"name": str, "confidence": float},
            "severity": {"name": str, "confidence": float},
            "inference_time_ms": float,
        }
        """
        start_time = time.time()

        if self.backend == "pytorch":
            result = self._predict_pytorch(image)
        elif self.backend == "onnx":
            result = self._predict_onnx(image)
        else:
            result = self._predict_trt(image)

        inference_time = (time.time() - start_time) * 1000
        result["inference_time_ms"] = round(inference_time, 2)

        return result

    def _predict_pytorch(self, image) -> Dict:
        """PyTorch推理"""
        input_tensor = self.preprocess(image).to(self.device)

        outputs = self.model(input_tensor)

        # 获取预测结果
        crop_prob = torch.softmax(outputs["crop"], dim=1)
        disease_prob = torch.softmax(outputs["disease"], dim=1)
        severity_prob = torch.softmax(outputs["severity"], dim=1)

        crop_conf, crop_idx = crop_prob.max(1)
        disease_conf, disease_idx = disease_prob.max(1)
        severity_conf, severity_idx = severity_prob.max(1)

        return {
            "crop": {"id": crop_idx.item(), "confidence": round(crop_conf.item() * 100, 2)},
            "disease": {"id": disease_idx.item(), "confidence": round(disease_conf.item() * 100, 2)},
            "severity": {"id": severity_idx.item(), "confidence": round(severity_conf.item() * 100, 2)},
        }

    def _predict_onnx(self, image) -> Dict:
        """ONNX推理"""
        input_tensor = self.preprocess(image).numpy()
        outputs = self.session.run(None, {self.input_name: input_tensor})

        crop_out, disease_out, severity_out = outputs

        crop_prob = self._softmax(crop_out[0])
        disease_prob = self._softmax(disease_out[0])
        severity_prob = self._softmax(severity_out[0])

        return {
            "crop": {"id": int(crop_prob.argmax()), "confidence": round(float(crop_prob.max()) * 100, 2)},
            "disease": {"id": int(disease_prob.argmax()), "confidence": round(float(disease_prob.max()) * 100, 2)},
            "severity": {"id": int(severity_prob.argmax()), "confidence": round(float(severity_prob.max()) * 100, 2)},
        }

    def _predict_trt(self, image) -> Dict:
        """TensorRT推理"""
        # TensorRT推理逻辑（略，需根据实际引擎实现）
        raise NotImplementedError("TensorRT推理需要CUDA内存管理")

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()

    def batch_predict(self, images: List[Union[str, np.ndarray]]) -> List[Dict]:
        """批量推理"""
        return [self.predict(img) for img in images]

    def benchmark(self, num_runs: int = 100, warmup: int = 10):
        """性能基准测试"""
        dummy_input = torch.randn(1, 3, self.img_size, self.img_size).to(self.device)

        # Warmup
        for _ in range(warmup):
            if self.backend == "pytorch":
                self.model(dummy_input)

        # Benchmark
        times = []
        for _ in range(num_runs):
            start = time.time()
            if self.backend == "pytorch":
                self.model(dummy_input)
            times.append((time.time() - start) * 1000)

        times = np.array(times)
        print(f"\n{'='*60}")
        print("推理性能基准测试")
        print(f"{'='*60}")
        print(f"后端: {self.backend}")
        print(f"图像尺寸: {self.img_size}x{self.img_size}")
        print(f"测试次数: {num_runs}")
        print(f"平均延迟: {times.mean():.2f} ms")
        print(f"中位延迟: {np.median(times):.2f} ms")
        print(f"最小延迟: {times.min():.2f} ms")
        print(f"最大延迟: {times.max():.2f} ms")
        print(f"P95延迟: {np.percentile(times, 95):.2f} ms")
        print(f"吞吐量: {1000/times.mean():.1f} FPS")
        print(f"{'='*60}")

        return {
            "mean_ms": round(times.mean(), 2),
            "median_ms": round(np.median(times), 2),
            "min_ms": round(times.min(), 2),
            "max_ms": round(times.max(), 2),
            "p95_ms": round(np.percentile(times, 95), 2),
            "fps": round(1000 / times.mean(), 1),
        }


def export_onnx(model_path: str, output_path: str, img_size: int = 224):
    """导出ONNX模型"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.lightweight_cnn import TropicalPestNet

    model = TropicalPestNet(num_classes=42, num_crops=15)
    checkpoint = torch.load(model_path, map_location="cpu")
    model.load_state_dict(checkpoint.get("model", checkpoint))
    model.eval()

    dummy_input = torch.randn(1, 3, img_size, img_size)

    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=11,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["crop", "disease", "severity"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "crop": {0: "batch_size"},
            "disease": {0: "batch_size"},
            "severity": {0: "batch_size"},
        },
    )
    print(f"ONNX模型已导出: {output_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="模型路径")
    parser.add_argument("--backend", default="pytorch", choices=["pytorch", "onnx", "tensorrt"])
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--benchmark", action="store_true", help="运行基准测试")
    parser.add_argument("--export-onnx", type=str, help="导出ONNX模型路径")
    args = parser.parse_args()

    if args.export_onnx:
        export_onnx(args.model, args.export_onnx)
    else:
        engine = InferenceEngine(args.model, args.backend, args.device)
        if args.benchmark:
            engine.benchmark()
        else:
            # 测试推理
            result = engine.benchmark(num_runs=50)
            print(result)
