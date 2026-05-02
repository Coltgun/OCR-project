# Next Steps

## Current Status
ARCH-001 complete. ARCH-002 (Define All ABCs) is next.

## Up Next
- [ ] ENV-001: Verify environment (run verify_env.py with chinese-ocr conda env active)
  - ℹ️ Current Python: 3.10.6. Must be 3.11. Create `chinese-ocr` conda env with Python 3.11.
  - ℹ️ PaddlePaddle 3.3.0 + PaddleOCR already installed in current env, GPU detected OK.
  - ℹ️ CUDA 13.1 driver — GPU working despite version mismatch. See KNOWN_ISSUES.md.
  - ℹ️ Missing packages: PySide6, pynput, pycorrector, datasketch, sentence-transformers, gitpython, openai, opencc, jieba.
  - ℹ️ PaddlePaddle 3.3.0 API change: `use_gpu` → `device=`, `use_angle_cls` → `use_textline_orientation`.
- [ ] ARCH-002: Define All ABCs (OCREngine, PostProcessStage, OutputFormatter, InputSource, LLMProvider + module stubs)
- [ ] ARCH-003: VRAM Tier Configuration (ConfigManager, file_utils, logging, data files)
## Completed
- [x] ARCH-001: Core Registry System — core/registry.py, core/vram_manager.py, core/event_bus.py (58 tests passing)
