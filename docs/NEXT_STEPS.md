# Next Steps

## Current Status
FEAT-epub complete. 348 tests passing. Ready for FEAT-main-window (main Qt application window + session dialog).

## Up Next
- [ ] FEAT-main-window: Main Qt application window, session start dialog, tray/status bar, wiring StateMachine + HotkeyListener + Pipeline + EpubFormatter
## Completed
- [x] ARCH-001: Core Registry System — core/registry.py, core/vram_manager.py, core/event_bus.py (58 tests passing)
- [x] ARCH-002: Define All ABCs — OCREngine, PostProcessStage, OutputFormatter, InputSource, LLMProvider + 4 module stubs (77 tests passing)
- [x] ARCH-003: VRAM Tier Configuration — ConfigManager, file_utils, logging_config, confusion_table.json, init_from_config() (135 tests passing)
- [x] ENV-001: chinese-ocr conda env created (Python 3.11.15), all packages verified. Architecture constraint documented: torch+paddle must not share a process (cuDNN DLL conflict).
- [x] FEAT-capture: CaptureSession, StateMachine, HotkeyListener, ScreenCapture, CaptureOverlay, RegionBorderOverlay (215 tests passing).
- [x] FEAT-ocr-engine: PaddleOCREngine (registry, VRAM lifecycle, parse_results, quad_to_bbox), OCRWorker subprocess (237 tests passing).
- [x] FEAT-pipeline: CleanupStage (1A-1F), RuleCorrectionsStage (confusion table, pattern fixes), Pipeline orchestrator (6 modes, skip-unregistered). (318 tests passing).
- [x] FEAT-epub: EpubFormatter (registry, numeric chapter order, CSS, metadata, in-memory BytesIO output). Bug fixed: ebooklib xml-decl lxml parse issue. (348 tests passing).
