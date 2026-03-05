"""
GPU Utilization Audit — RTX 3050 Laptop 6GB
Run: python gpu_audit.py
"""

import torch
import time
import sys

print("=" * 60)
print("GPU AUDIT — RTX 3050 Laptop 6GB")
print("=" * 60)

print(f"\n✅ CUDA available    : {torch.cuda.is_available()}")
print(f"✅ CUDA version      : {torch.version.cuda}")
print(f"✅ PyTorch version   : {torch.__version__}")
print(f"✅ GPU name          : {torch.cuda.get_device_name(0)}")

props = torch.cuda.get_device_properties(0)
print(f"✅ VRAM              : {props.total_memory / 1024**3:.1f} GB")
print(f"✅ SM count          : {props.multi_processor_count}")
print(f"✅ Compute capability: {props.major}.{props.minor}")
print(f"✅ FP16 Tensor Cores : {props.major >= 7}")

alloc = torch.cuda.memory_allocated(0) / 1024**2
reserved = torch.cuda.memory_reserved(0) / 1024**2
print(f"\n📊 GPU memory allocated : {alloc:.1f} MB")
print(f"📊 GPU memory reserved  : {reserved:.1f} MB")
print(f"📊 Free VRAM estimate   : {(props.total_memory/1024**2 - reserved):.0f} MB")

print("\n🔥 FP32 vs FP16 Tensor Core benchmark...")
a = torch.randn(4096, 4096, device='cuda')
b = torch.randn(4096, 4096, device='cuda')
torch.cuda.synchronize()
t0 = time.perf_counter()
for _ in range(50):
    c = torch.mm(a, b)
torch.cuda.synchronize()
fps32 = 50 / (time.perf_counter() - t0)

a16, b16 = a.half(), b.half()
torch.cuda.synchronize()
t0 = time.perf_counter()
for _ in range(50):
    c16 = torch.mm(a16, b16)
torch.cuda.synchronize()
fps16 = 50 / (time.perf_counter() - t0)

print(f"   FP32 : {fps32:.0f} ops/sec")
print(f"   FP16 : {fps16:.0f} ops/sec  → {fps16/fps32:.1f}x speedup via Tensor Cores")

print("\n🔍 YOLO inference benchmark (FP32 vs FP16)...")
try:
    from ultralytics import YOLO
    import numpy as np

    dummy = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    model = YOLO('yolov8n.pt')
    model.to('cuda:0')

    # Warmup
    for _ in range(3):
        model.predict(dummy, device='cuda:0', verbose=False)

    # FP32
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(30):
        model.predict(dummy, device='cuda:0', verbose=False)
    torch.cuda.synchronize()
    fp32_fps = 30 / (time.perf_counter() - t0)
    print(f"   FP32 : {fp32_fps:.1f} FPS")

    # FP16 — reload model fresh so weights are clean, pass half=True to predict()
    # (ultralytics handles input casting internally when half=True is set)
    model_fp16 = YOLO('yolov8n.pt')
    model_fp16.to('cuda:0')
    # Warmup in FP16 mode
    for _ in range(3):
        model_fp16.predict(dummy, device='cuda:0', half=True, verbose=False)
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(30):
        model_fp16.predict(dummy, device='cuda:0', half=True, verbose=False)
    torch.cuda.synchronize()
    fp16_fps = 30 / (time.perf_counter() - t0)
    print(f"   FP16 : {fp16_fps:.1f} FPS  → {fp16_fps/fp32_fps:.1f}x faster")

    alloc_after = torch.cuda.memory_allocated(0) / 1024**2
    reserved_after = torch.cuda.memory_reserved(0) / 1024**2
    print(f"\n📊 VRAM after both models loaded:")
    print(f"   Allocated : {alloc_after:.0f} MB")
    print(f"   Reserved  : {reserved_after:.0f} MB")
    print(f"   Remaining : {6144 - reserved_after:.0f} MB free for ByteTrack state")
    del model_fp16

except Exception as e:
    print(f"   Skipped: {e}")

print("\n" + "=" * 60)
print("RESULTS GUIDE")
print("=" * 60)
print("  FP16 speedup < 1.5x  → Tensor Cores not activating (fix: use .half())")
print("  FP16 speedup 2-4x    → Tensor Cores working correctly ✅")
print("  YOLO FP16 > 60 FPS   → Excellent, throughput is not bottleneck")
print("  YOLO FP16 < 30 FPS   → Consider TensorRT export")
print("  VRAM remaining < 500 → Reduce imgsz or disable stabilizer")
print("=" * 60)