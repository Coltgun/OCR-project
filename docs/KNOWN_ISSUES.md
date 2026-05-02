# Known Issues

Track active bugs here with reproduction steps. Remove entries when resolved.

## Active Issues

### CUDA 13.1 Driver — PaddlePaddle GPU Incompatibility
**Discovered:** 2026-05-02  
**Severity:** Blocker for GPU-accelerated OCR  
**Details:** `nvidia-smi` reports Driver 591.74, CUDA Version 13.1. PaddlePaddle GPU 3.0.0 only supports CUDA up to 12.9. Installing from `cu126` index will install successfully but GPU acceleration may not work.  
**Reproduction:** Run `nvidia-smi` — top-right shows `CUDA Version: 13.1`.  
**Workarounds (pick one):**
1. Install CUDA 12.x runtime toolkit alongside the driver (Windows supports multiple CUDA versions). Set `CUDA_PATH` to the 12.x install. PaddlePaddle will use it.
2. Use `paddleocr` with `use_gpu=False` (CPU mode) until a CUDA 13.x-compatible PaddlePaddle release is available.
3. Monitor https://www.paddlepaddle.org.cn for a cu131 package index release.

**Recommended action before ENV-001:** Install CUDA 12.6 Toolkit from https://developer.nvidia.com/cuda-12-6-0-download-archive alongside the existing driver. Do NOT uninstall the driver.
