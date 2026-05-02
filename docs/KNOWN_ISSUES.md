# Known Issues

Track active bugs here with reproduction steps. Remove entries when resolved.

## Active Issues

### CUDA 13.1 Driver — PaddlePaddle Compatibility Status
**Discovered:** 2026-05-02  
**Severity:** Monitor only (GPU appears functional)  
**Details:** `nvidia-smi` reports Driver 591.74, CUDA Version 13.1. PaddlePaddle documentation states support up to CUDA 12.9. However, `verify_env.py` confirms that PaddlePaddle 3.3.0 (installed) IS compiled with CUDA and detects the GPU (1 GPU found). GPU acceleration appears to work despite the version mismatch.  
**Status:** Functional — verify during actual OCR runs. If OOM or CUDA errors appear, install CUDA 12.6 Toolkit alongside the driver as a fallback.  
**Also note:** PaddlePaddle 3.3.0 is installed (newer than the 3.0.0 documented in guidelines). API has changed:  
  - `use_gpu` → `device="gpu"` or `device="cpu"`  
  - `use_angle_cls` → `use_textline_orientation`  
  
  These deprecations are already reflected in `scripts/verify_env.py` and will need to be applied in `ocr/engines/paddle_engine.py` (ARCH-002).
