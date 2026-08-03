"""
智农慧眼 - Jetson Nano 边缘端部署脚本
功能：
  - 加载优化后的TensorRT/ONNX模型
  - 接收摄像头/图像输入
  - 实时推理并输出结果
  - 支持MQTT上报到云端
  - 本地LCD屏幕显示结果

硬件要求：
  - NVIDIA Jetson Nano 4GB
  - CSI/USB 摄像头
  - 可选：2.8寸LCD显示屏
"""
import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

import numpy as np
import cv2

# 推理后端选择
BACKEND = os.getenv("ZHINONG_BACKEND", "onnx")

if BACKEND == "tensorrt":
    try:
        import tensorrt as trt
        import pycuda.driver as cuda
        import pycuda.autoinit
        HAS_TRT = True
    except ImportError:
        HAS_TRT = False
        print("警告: TensorRT未安装，回退到ONNX")
        BACKEND = "onnx"

if BACKEND == "onnx":
    import onnxruntime as ort
    HAS_ONNX = True

# MQTT上报（可选）
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False


class EdgeInferenceEngine:
    """边缘端推理引擎"""

    def __init__(
        self,
        model_path: str,
        backend: str = "onnx",
        img_size: int = 224,
        device_id: int = 0,
    ):
        self.backend = backend
        self.img_size = img_size
        self.device_id = device_id

        # 预处理参数
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

        # 加载模型
        if backend == "tensorrt" and HAS_TRT:
            self._load_tensorrt(model_path)
        elif backend == "onnx" and HAS_ONNX:
            self._load_onnx(model_path)
        else:
            raise RuntimeError(f"不支持的后端: {backend}")

        print(f"边缘推理引擎就绪: backend={backend}, img_size={img_size}")

    def _load_tensorrt(self, engine_path: str):
        """加载TensorRT引擎"""
        logger = trt.Logger(trt.Logger.WARNING)
        with open(engine_path, "rb") as f:
            runtime = trt.Runtime(logger)
            self.engine = runtime.deserialize_cuda_engine(f.read())
        self.context = self.engine.create_execution_context()

        # 分配GPU内存
        self.d_input = cuda.mem_alloc(1 * 3 * self.img_size * self.img_size * 4)
        self.d_crop = cuda.mem_alloc(1 * 15 * 4)
        self.d_disease = cuda.mem_alloc(1 * 42 * 4)
        self.d_severity = cuda.mem_alloc(1 * 3 * 4)
        self.bindings = [int(self.d_input), int(self.d_crop), int(self.d_disease), int(self.d_severity)]
        self.stream = cuda.Stream()

        self.input_buffer = np.empty((1, 3, self.img_size, self.img_size), dtype=np.float32)
        self.crop_buffer = np.empty((1, 15), dtype=np.float32)
        self.disease_buffer = np.empty((1, 42), dtype=np.float32)
        self.severity_buffer = np.empty((1, 3), dtype=np.float32)

    def _load_onnx(self, onnx_path: str):
        """加载ONNX模型"""
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.session = ort.InferenceSession(onnx_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """图像预处理（OpenCV格式 BGR → RGB → Normalize）"""
        # Resize
        img = cv2.resize(image, (self.img_size, self.img_size))
        # BGR → RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # Normalize
        img = img.astype(np.float32) / 255.0
        img = (img - self.mean) / self.std
        # HWC → CHW
        img = np.transpose(img, (2, 0, 1))
        # Add batch dimension
        img = np.expand_dims(img, axis=0)
        return img.astype(np.float32)

    def infer(self, image: np.ndarray) -> dict:
        """单次推理"""
        input_tensor = self.preprocess(image)
        start = time.time()

        if self.backend == "tensorrt":
            np.copyto(self.input_buffer, input_tensor)
            cuda.memcpy_htod_async(self.d_input, self.input_buffer, self.stream)
            self.context.execute_async_v2(bindings=self.bindings, stream_handle=self.stream.handle)
            cuda.memcpy_dtoh_async(self.crop_buffer, self.d_crop, self.stream)
            cuda.memcpy_dtoh_async(self.disease_buffer, self.d_disease, self.stream)
            cuda.memcpy_dtoh_async(self.severity_buffer, self.d_severity, self.stream)
            self.stream.synchronize()

            crop_out = self.crop_buffer[0]
            disease_out = self.disease_buffer[0]
            severity_out = self.severity_buffer[0]

        else:  # ONNX
            outputs = self.session.run(None, {self.input_name: input_tensor})
            crop_out = outputs[0][0]
            disease_out = outputs[1][0]
            severity_out = outputs[2][0]

        inference_time = (time.time() - start) * 1000

        # Softmax
        def softmax(x):
            exp_x = np.exp(x - np.max(x))
            return exp_x / exp_x.sum()

        crop_prob = softmax(crop_out)
        disease_prob = softmax(disease_out)
        severity_prob = softmax(severity_out)

        return {
            "crop_id": int(crop_prob.argmax()),
            "crop_conf": float(crop_prob.max()),
            "disease_id": int(disease_prob.argmax()),
            "disease_conf": float(disease_prob.max()),
            "severity_id": int(severity_prob.argmax()),
            "severity_conf": float(severity_prob.max()),
            "inference_time_ms": round(inference_time, 2),
        }


class MQTTReporter:
    """MQTT数据上报"""
    def __init__(self, broker: str = "localhost", port: int = 1883, topic: str = "zhinong/detection"):
        if not HAS_MQTT:
            print("MQTT未安装，跳过上报")
            return

        self.client = mqtt.Client()
        self.client.connect(broker, port)
        self.topic = topic
        print(f"MQTT已连接: {broker}:{port}")

    def publish(self, data: dict):
        if not HAS_MQTT:
            return
        payload = json.dumps(data, ensure_ascii=False)
        self.client.publish(self.topic, payload)


def draw_result(image: np.ndarray, result: dict, crop_names: list, disease_names: list) -> np.ndarray:
    """在图像上绘制推理结果"""
    img = image.copy()
    h, w = img.shape[:2]

    # 绘制信息面板
    panel_h = 120
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    img = cv2.addWeighted(overlay, 0.7, img, 0.3, 0)

    # 文本
    crop = crop_names[result["crop_id"]] if result["crop_id"] < len(crop_names) else "未知"
    disease = disease_names[result["disease_id"]] if result["disease_id"] < len(disease_names) else "未知"
    severity = ["轻度", "中度", "重度"][result["severity_id"]]

    color = (0, 255, 0) if result["severity_id"] == 0 else (0, 165, 255) if result["severity_id"] == 1 else (0, 0, 255)

    cv2.putText(img, f"作物: {crop} ({result['crop_conf']*100:.1f}%)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(img, f"病害: {disease} ({result['disease_conf']*100:.1f}%)", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.putText(img, f"严重: {severity} | 延迟: {result['inference_time_ms']:.1f}ms", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    return img


def main():
    parser = argparse.ArgumentParser(description="智农慧眼边缘端部署")
    parser.add_argument("--model", type=str, required=True, help="模型路径(.onnx或.trt)")
    parser.add_argument("--backend", type=str, default=BACKEND, choices=["onnx", "tensorrt"])
    parser.add_argument("--source", type=str, default="0", help="视频源(0=摄像头, path=视频/图像)")
    parser.add_argument("--img-size", type=int, default=224)
    parser.add_argument("--save", action="store_true", help="保存结果视频")
    parser.add_argument("--mqtt", action="store_true", help="启用MQTT上报")
    parser.add_argument("--show", action="store_true", default=True, help="显示结果")
    parser.add_argument("--interval", type=float, default=1.0, help="推理间隔(秒)")
    args = parser.parse_args()

    # 类别名称
    crop_names = ["芒果", "荔枝", "槟榔", "香蕉", "菠萝", "火龙果", "木瓜", "椰子", "橡胶", "胡椒",
                  "咖啡", "茶叶", "甘蔗", "木薯", "剑麻"]
    disease_names = [
        "芒果炭疽病", "芒果白粉病", "芒果细菌性角斑病", "芒果介壳虫", "芒果蓟马", "芒果瘿螨",
        "荔枝霜疫霉病", "荔枝炭疽病", "荔枝蝽", "荔枝蒂蛀虫", "荔枝瘿螨",
        "槟榔黄化病", "槟榔炭疽病", "槟榔细菌性条斑病", "槟榔红脉穗螟", "槟榔蚧壳虫",
        "香蕉枯萎病", "香蕉叶斑病", "香蕉黑星病", "香蕉象甲", "香蕉蚜虫",
        "菠萝心腐病", "菠萝黑腐病", "菠萝粉蚧", "菠萝红蜘蛛",
        "火龙果溃疡病", "火龙果炭疽病", "火龙果蜗牛", "火龙果介壳虫",
        "木瓜花叶病", "木瓜炭疽病", "木瓜红蜘蛛", "木瓜介壳虫",
        "椰子红环腐病", "橡胶白粉病", "胡椒瘟病", "咖啡锈病",
        "茶叶茶饼病", "甘蔗赤腐病", "木薯细菌性枯萎病", "剑斑马纹病", "健康",
    ]

    # 初始化引擎
    engine = EdgeInferenceEngine(args.model, args.backend, args.img_size)

    # MQTT
    reporter = MQTTReporter() if args.mqtt else None

    # 打开视频源
    if args.source.isdigit():
        cap = cv2.VideoCapture(int(args.source))
    else:
        cap = cv2.VideoCapture(args.source)

    if not cap.isOpened():
        print(f"无法打开视频源: {args.source}")
        return

    # 视频保存
    writer = None
    if args.save:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = 15
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter("output.mp4", fourcc, fps, (w, h))

    print("开始推理，按 'q' 退出...")
    last_infer_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_time = time.time()

        # 按间隔推理
        if current_time - last_infer_time >= args.interval:
            result = engine.infer(frame)
            last_infer_time = current_time

            # 上报
            if reporter:
                reporter.publish({
                    "timestamp": datetime.now().isoformat(),
                    "device_id": "jetson-nano-01",
                    **result,
                })

            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"{crop_names[result['crop_id']]} | "
                  f"{disease_names[result['disease_id']]} | "
                  f"{result['inference_time_ms']:.1f}ms")

        # 绘制结果
        if args.show or args.save:
            display = draw_result(frame, result, crop_names, disease_names)
            if args.save and writer:
                writer.write(display)
            if args.show:
                cv2.imshow("智农慧眼 - 边缘端推理", display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()
    print("边缘端推理结束")


if __name__ == "__main__":
    main()
