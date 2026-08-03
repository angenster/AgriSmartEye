"""
智农慧眼 - 边缘端模型优化
将PyTorch模型转换为ONNX和TensorRT格式，适配Jetson Nano部署
流程：PyTorch → ONNX → TensorRT (FP16/INT8)
"""
import os
import sys
import argparse
from pathlib import Path

import torch
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "ai-model"))
from models.lightweight_cnn import TropicalPestNet


def export_onnx(
    model_path: str,
    output_path: str,
    img_size: int = 224,
    simplify: bool = True,
):
    """导出ONNX模型"""
    print(f"导出ONNX: {output_path}")

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

    # 简化模型
    if simplify:
        try:
            import onnx
            from onnxsim import simplify as onnx_simplify

            print("简化ONNX模型...")
            onnx_model = onnx.load(output_path)
            simplified, check = onnx_simplify(onnx_model)
            if check:
                onnx.save(simplified, output_path)
                print("✓ ONNX简化完成")
            else:
                print("× ONNX简化失败，使用原始模型")
        except ImportError:
            print("未安装onnx-simplifier，跳过简化")

    # 验证
    import onnx
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print(f"✓ ONNX验证通过: {output_path}")


def build_tensorrt_engine(
    onnx_path: str,
    output_path: str,
    fp16: bool = True,
    int8: bool = False,
    workspace_mb: int = 512,
    img_size: int = 224,
):
    """构建TensorRT引擎"""
    try:
        import tensorrt as trt
    except ImportError:
        print("TensorRT未安装，跳过引擎构建")
        return

    print(f"构建TensorRT引擎: {output_path}")
    print(f"FP16: {fp16}, INT8: {int8}")

    logger = trt.Logger(trt.Logger.INFO)
    builder = trt.Builder(logger)
    network = builder.create_network(
        1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    )
    parser = trt.OnnxParser(network, logger)

    # 解析ONNX
    with open(onnx_path, "rb") as f:
        if not parser.parse(f.read()):
            for error in range(parser.num_errors):
                print(parser.get_error(error))
            raise RuntimeError("ONNX解析失败")

    # 配置
    config = builder.create_builder_config()
    config.max_workspace_size = workspace_mb * 1024 * 1024

    if fp16:
        config.set_flag(trt.BuilderFlag.FP16)
        print("启用FP16精度")

    if int8:
        config.set_flag(trt.BuilderFlag.INT8)
        print("启用INT8精度（需校准）")
        # TODO: 添加INT8校准器

    # 构建引擎
    profile = builder.create_optimization_profile()
    profile.set_shape(
        "input",
        min=(1, 3, img_size, img_size),
        opt=(1, 3, img_size, img_size),
        max=(8, 3, img_size, img_size),
    )
    config.add_optimization_profile(profile)

    print("开始构建引擎...")
    engine = builder.build_engine(network, config)

    if engine is None:
        raise RuntimeError("TensorRT引擎构建失败")

    # 保存引擎
    with open(output_path, "wb") as f:
        f.write(engine.serialize())

    print(f"✓ TensorRT引擎构建完成: {output_path}")
    print(f"  引擎大小: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")


def benchmark_jetson(engine_path: str, num_runs: int = 100):
    """Jetson Nano性能测试"""
    import tensorrt as trt
    import pycuda.driver as cuda
    import pycuda.autoinit

    logger = trt.Logger(trt.Logger.WARNING)

    with open(engine_path, "rb") as f:
        runtime = trt.Runtime(logger)
        engine = runtime.deserialize_cuda_engine(f.read())

    context = engine.create_execution_context()

    # 分配内存
    input_shape = (1, 3, 224, 224)
    output_shapes = [(1, 15), (1, 42), (1, 3)]

    d_input = cuda.mem_alloc(np.prod(input_shape) * np.dtype(np.float32).itemsize)
    d_outputs = [cuda.mem_alloc(np.prod(s) * np.dtype(np.float32).itemsize) for s in output_shapes]

    bindings = [int(d_input)] + [int(d) for d in d_outputs]

    stream = cuda.Stream()

    # 测试
    import time
    times = []

    dummy = np.random.randn(*input_shape).astype(np.float32)

    for _ in range(num_runs):
        start = time.time()
        cuda.memcpy_htod_async(d_input, dummy, stream)
        context.execute_async_v2(bindings=bindings, stream_handle=stream.handle)
        for d_out in d_outputs:
            cuda.memcpy_dtoh_async(np.empty(1), d_out, stream)
        stream.synchronize()
        times.append((time.time() - start) * 1000)

    times = np.array(times)
    print(f"\n{'='*60}")
    print("Jetson Nano TensorRT性能测试")
    print(f"{'='*60}")
    print(f"平均延迟: {times.mean():.2f} ms")
    print(f"P95延迟: {np.percentile(times, 95):.2f} ms")
    print(f"吞吐量: {1000/times.mean():.1f} FPS")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="边缘端模型优化")
    parser.add_argument("--model", type=str, required=True, help="PyTorch模型路径")
    parser.add_argument("--output-dir", type=str, default="./optimized", help="输出目录")
    parser.add_argument("--img-size", type=int, default=224, help="输入图像尺寸")
    parser.add_argument("--fp16", action="store_true", default=True, help="启用FP16")
    parser.add_argument("--int8", action="store_true", help="启用INT8（需校准数据）")
    parser.add_argument("--benchmark", action="store_true", help="运行性能测试")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 1. 导出ONNX
    onnx_path = os.path.join(args.output_dir, "zhinong.onnx")
    export_onnx(args.model, onnx_path, args.img_size)

    # 2. 构建TensorRT引擎
    try:
        trt_path = os.path.join(args.output_dir, "zhinong.trt")
        build_tensorrt_engine(
            onnx_path, trt_path,
            fp16=args.fp16, int8=args.int8,
            img_size=args.img_size,
        )

        if args.benchmark:
            benchmark_jetson(trt_path)
    except Exception as e:
        print(f"TensorRT构建失败: {e}")
        print("模型已导出为ONNX，可手动转换为TensorRT")

    print("\n优化完成！")
    print(f"输出目录: {args.output_dir}")


if __name__ == "__main__":
    main()
