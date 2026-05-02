# Next Steps

## Current Status
FEAT-ocr-engine complete. 237 tests passing. Ready for FEAT-pipeline (OCR post-processing stages).

## Up Next
- [ ] FEAT-pipeline: OCR post-processing pipeline (Stage 1 Cleanup, Stage 2A Rule Corrections, pipeline orchestrator, LOCAL_FAST mode)
## Completed
- [x] ARCH-001: Core Registry System — core/registry.py, core/vram_manager.py, core/event_bus.py (58 tests passing)
- [x] ARCH-002: Define All ABCs — OCREngine, PostProcessStage, OutputFormatter, InputSource, LLMProvider + 4 module stubs (77 tests passing)
- [x] ARCH-003: VRAM Tier Configuration — ConfigManager, file_utils, logging_config, confusion_table.json, init_from_config() (135 tests passing)
- [x] ENV-001: chinese-ocr conda env created (Python 3.11.15), all packages verified. Architecture constraint documented: torch+paddle must not share a process (cuDNN DLL conflict).
- [x] FEAT-capture: CaptureSession, StateMachine, HotkeyListener, ScreenCapture, CaptureOverlay, RegionBorderOverlay (215 tests passing).
- [x] FEAT-ocr-engine: PaddleOCREngine (registry, VRAM lifecycle, parse_results, quad_to_bbox), OCRWorker subprocess (237 tests passing).
