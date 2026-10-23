"""
智农慧眼 - 推理引擎
支持：PyTorch、ONNX、TensorRT多后端推理
目标：边缘端实时推理 (< 200ms@Jetson Nano)

输出契约（predict 返回值）：
    {
      "crop":     {"id": int, "name": str, "confidence": float, "topk": [...]},
      "disease":  {"id": int, "name": str, "confidence": float, "topk": [...]},
      "severity": {"id": int, "name": str, "confidence": float},
      "inference_time_ms": float,
      "backend": str,
      "is_demo": bool,   # True 表示未加载真实权重，输出不可用于业务判断
    }
    置信度统一为 0~1。topk 仅对 disease 计算（Agent 的升级仲裁依赖 top1-top2 间距）。
"""
import os
import sys
import time
import importlib.util
from pathlib import Path
from typing import Union, List, Dict, Optional

import torch
import torch.nn as nn
import numpy as np
from PIL import Image
import torchvision.transforms as T

# 标签定义在 ai-model/labels.py，与训练侧共用同一份
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from labels import (  # noqa: E402
    CROP_CLASSES, DISEASE_CLASSES, LABELS_VERSION, SEVERITY_TRAINED,
    crop_name, crop_of_label, disease_name, severity_name,
)

# 模型类缓存（见 load_model_class）
_MODEL_CLASS = None


def load_model_class():
    """按文件路径加载 TropicalPestNet。

    不能用 `from models.lightweight_cnn import TropicalPestNet`：本项目里
    backend/models.py 与 ai-model/models/ 同名，而后端进程启动时
    sys.modules["models"] 已被 backend/models.py 占用，届时会报
    "No module named 'models.lightweight_cnn'; 'models' is not a package"。
    按路径加载可彻底避开这次命名冲突。
    """
    global _MODEL_CLASS
    if _MODEL_CLASS is None:
        model_file = Path(__file__).resolve().parent.parent / "models" / "lightweight_cnn.py"
        spec = importlib.util.spec_from_file_location("zhinong_lightweight_cnn", model_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # 注册后再执行，便于 dataclass/pickle 解析
        spec.loader.exec_module(module)
        _MODEL_CLASS = module.TropicalPestNet
    return _MODEL_CLASS

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


def resolve_device(device: str) -> str:
    """把 "auto" 解析为实际可用设备；显式指定 cuda 但不可用时回退 CPU 并告警。

    原实现直接 torch.zeros(...).to("cuda")，在无 GPU 机器上会直接抛错。
    """
    if device != "auto":
        if device.startswith("cuda") and not torch.cuda.is_available():
            print(f"[WARN] 指定 device={device} 但 CUDA 不可用，回退 CPU")
            return "cpu"
        return device
    return "cuda" if torch.cuda.is_available() else "cpu"


def _topk_entries(prob: torch.Tensor, k: int, namer) -> List[Dict]:
    """从概率向量取 top-k，返回带类别名的列表（降序）"""
    k = min(k, prob.shape[-1])
    values, indices = prob.topk(k)
    return [
        {"id": int(i), "name": namer(int(i)), "confidence": round(float(v), 4)}
        for v, i in zip(values, indices)
    ]


class InferenceEngine:
    """智农慧眼推理引擎"""

    def __init__(
        self,
        model_path: Optional[str] = None,
        backend: str = "pytorch",
        device: str = "auto",
        img_size: int = 224,
        num_classes: int = len(DISEASE_CLASSES),
        num_crops: int = len(CROP_CLASSES),
        topk: int = 5,
        allow_demo: bool = False,
    ):
        self.backend = backend.lower()
        self.device = resolve_device(device)
        self.img_size = img_size
        self.num_classes = num_classes
        self.num_crops = num_crops
        self.topk = topk
        # is_demo=True 表示未加载训练权重（随机分类头），输出不可用于业务判断
        self.is_demo = False
        self.model_path = model_path
        # 版本号优先取权重内记录的 version，其次用文件名
        self.version = "unknown"
        # 训练集里真实出现过的类别；None 表示不限制（如 demo 模式）
        self.trained_indices = None
        # 是否强制病害类别与作物头一致（默认开启）
        self.crop_consistency = os.getenv("MODEL_CROP_CONSISTENCY", "true").lower() in (
            "1", "true", "yes", "on"
        )

        # 预处理必须与训练时的验证变换一致：先放大再中心裁剪。
        # 直接用 Resize((224,224)) 会改变长宽比与裁剪范围，造成训练/推理分布偏移。
        self.transform = T.Compose([
            T.Resize(int(img_size * 1.14)),
            T.CenterCrop(img_size),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        # 加载模型
        if self.backend == "pytorch":
            self._load_pytorch(model_path, allow_demo=allow_demo)
        elif self.backend == "onnx":
            self._load_onnx(model_path)
        elif self.backend == "tensorrt":
            self._load_tensorrt(model_path)
        else:
            raise ValueError(f"不支持的后端: {backend}")

        print(
            f"推理引擎初始化完成: backend={backend}, device={self.device}"
            + ("[DEMO-未加载训练权重]" if self.is_demo else "")
        )

    def _load_pytorch(self, model_path: Optional[str], allow_demo: bool = False):
        """加载PyTorch模型

        model_path 为空或文件不存在时：仅当 allow_demo=True 才允许以
        ImageNet 预训练骨干 + 随机分类头启动（链路验证用），否则直接报错，
        避免"以为在用真模型"的静默失败。
        """
        TropicalPestNet = load_model_class()

        if not model_path or not os.path.exists(model_path):
            if not allow_demo:
                raise FileNotFoundError(
                    f"模型权重不存在: {model_path!r}。"
                    "如需以未训练权重跑通链路（结果不可用于业务判断），"
                    "请显式传 allow_demo=True。"
                )
            print(f"[WARN] 未找到权重 {model_path!r}，进入 DEMO 模式（随机分类头）")
            self.is_demo = True
            self.version = "demo-untrained"
            self.model = TropicalPestNet(self.num_classes, self.num_crops, pretrained=True)
            self.model = self.model.to(self.device).eval()
            return

        self.model = TropicalPestNet(self.num_classes, self.num_crops, pretrained=False)
        checkpoint = torch.load(model_path, map_location=self.device)

        # 权重里记录了训练时的类别表与版本；与当前代码不一致说明标签顺序可能错位，
        # 此时 argmax 出来的 id 会映射到错误的病名——必须硬失败而不是继续跑。
        if isinstance(checkpoint, dict):
            ckpt_disease = checkpoint.get("disease_classes")
            if ckpt_disease and list(ckpt_disease) != list(DISEASE_CLASSES):
                raise ValueError(
                    "权重与当前标签表不一致：\n"
                    f"  权重: {list(ckpt_disease)}\n"
                    f"  代码: {list(DISEASE_CLASSES)}\n"
                    "请用当前 labels.py 重新训练，或切回对应版本的代码。"
                )
            ckpt_version = checkpoint.get("labels_version")
            if ckpt_version and ckpt_version != LABELS_VERSION:
                print(f"[WARN] 权重标签版本 {ckpt_version} != 当前 {LABELS_VERSION}")

            # 零样本类别屏蔽：训练集里没出现过的类，其分类头权重是随机初始化的，
            # 会在低置信区间吸收错误预测。推理时把它们置零再归一化。
            trained = checkpoint.get("trained_classes")
            if trained:
                self.trained_indices = {i for i, d in enumerate(DISEASE_CLASSES) if d in set(trained)}
                missing = [d for d in DISEASE_CLASSES if d not in set(trained)]
                if missing:
                    print(f"[INFO] 屏蔽 {len(missing)} 个零样本类别: {missing}")

            self.version = checkpoint.get("version") or Path(model_path).stem

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
        if not model_path or not os.path.exists(model_path):
            raise FileNotFoundError(f"ONNX 模型不存在: {model_path!r}")

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
        单张图像推理。返回结构与量纲见模块 docstring（置信度 0~1，含类别名与 topk）。
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

    def _format_result(
        self,
        crop_prob: torch.Tensor,
        disease_prob: torch.Tensor,
        severity_prob: torch.Tensor,
    ) -> Dict:
        """把三个头的概率向量格式化为统一输出结构（各后端共用）"""
        # 屏蔽零样本类别后重新归一化，确保 top-k 与 margin 都只在有效类中排序
        if self.trained_indices is not None and disease_prob.numel() == len(DISEASE_CLASSES):
            mask = torch.zeros_like(disease_prob)
            for i in self.trained_indices:
                mask[i] = 1.0
            masked = disease_prob * mask
            if masked.sum() > 0:
                disease_prob = masked / masked.sum()

        # 作物一致性：病害标签自带作物前缀，与 crop 头不一致的组合在现实中不存在。
        # 跨域评测中芒果炭疽病有 9% 被误判成"香蕉黑星病"（跨作物），加这条约束
        # 可直接消除；"健康"没有作物前缀，始终保留。
        if self.crop_consistency and disease_prob.numel() == len(DISEASE_CLASSES):
            pred_crop = crop_name(int(crop_prob.argmax()))
            allowed = {
                i for i, d in enumerate(DISEASE_CLASSES)
                if crop_of_label(d) in (None, pred_crop)
            }
            if allowed:
                mask = torch.zeros_like(disease_prob)
                for i in allowed:
                    mask[i] = 1.0
                masked = disease_prob * mask
                if masked.sum() > 0:
                    disease_prob = masked / masked.sum()

        crop_top = _topk_entries(crop_prob, self.topk, crop_name)
        disease_top = _topk_entries(disease_prob, self.topk, disease_name)

        if SEVERITY_TRAINED:
            severity_top = _topk_entries(severity_prob, self.topk, severity_name)
        else:
            # 没有严重度训练数据：随机头输出任何等级都是编造，
            # 而且"重度"会误触发人工复核红线。这里显式返回"未评估"。
            severity_top = [{"id": -1, "name": "未评估", "confidence": 0.0}]

        return {
            "crop": {**crop_top[0], "topk": crop_top},
            "disease": {**disease_top[0], "topk": disease_top},
            "severity": {**severity_top[0], "topk": severity_top},
            "backend": self.backend,
            "is_demo": self.is_demo,
        }

    def _predict_pytorch(self, image) -> Dict:
        """PyTorch推理"""
        input_tensor = self.preprocess(image).to(self.device)

        outputs = self.model(input_tensor)

        # 取 batch 中第一张，概率化后交给统一格式化
        crop_prob = torch.softmax(outputs["crop"], dim=1)[0]
        disease_prob = torch.softmax(outputs["disease"], dim=1)[0]
        severity_prob = torch.softmax(outputs["severity"], dim=1)[0]

        return self._format_result(crop_prob, disease_prob, severity_prob)

    def _predict_onnx(self, image) -> Dict:
        """ONNX推理"""
        input_tensor = self.preprocess(image).numpy()
        outputs = self.session.run(None, {self.input_name: input_tensor})

        crop_out, disease_out, severity_out = outputs

        return self._format_result(
            torch.from_numpy(self._softmax(crop_out[0])),
            torch.from_numpy(self._softmax(disease_out[0])),
            torch.from_numpy(self._softmax(severity_out[0])),
        )

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
    TropicalPestNet = load_model_class()

    model = TropicalPestNet()
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
    parser.add_argument("--device", default="auto", help="推理设备，默认自动选择")
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
