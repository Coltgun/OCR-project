# Next Steps

## Current Status
FEAT-single-ocr complete. 410 passed, 9 skipped. Ready for FEAT-dedup (deduplication stage: MinHash near-duplicate detection).

## Up Next
- [ ] FEAT-dedup: Deduplication stage — MinHash near-duplicate detection (datasketch), plugs into pipeline as PostProcessStage
## Completed
- [x] ARCH-001: Core Registry System — core/registry.py, core/vram_manager.py, core/event_bus.py (58 tests passing)
- [x] ARCH-002: Define All ABCs — OCREngine, PostProcessStage, OutputFormatter, InputSource, LLMProvider + 4 module stubs (77 tests passing)
- [x] ARCH-003: VRAM Tier Configuration — ConfigManager, file_utils, logging_config, confusion_table.json, init_from_config() (135 tests passing)
- [x] ENV-001: chinese-ocr conda env created (Python 3.11.15), all packages verified. Architecture constraint documented: torch+paddle must not share a process (cuDNN DLL conflict).
- [x] FEAT-capture: CaptureSession, StateMachine, HotkeyListener, ScreenCapture, CaptureOverlay, RegionBorderOverlay (215 tests passing).
- [x] FEAT-ocr-engine: PaddleOCREngine (registry, VRAM lifecycle, parse_results, quad_to_bbox), OCRWorker subprocess (237 tests passing).
- [x] FEAT-pipeline: CleanupStage (1A-1F), RuleCorrectionsStage (confusion table, pattern fixes), Pipeline orchestrator (6 modes, skip-unregistered). (318 tests passing).
- [x] FEAT-epub: EpubFormatter (registry, numeric chapter order, CSS, metadata, in-memory BytesIO output). Bug fixed: ebooklib xml-decl lxml parse issue. (348 tests passing).
- [x] FEAT-main-window: MainWindow (menu, session/region/capture/OCR/export controls, state machine wiring), SessionDialog (digits-only validation, resume/overwrite), main.py entry point. conftest.py + gui pytest marker. Bug fixed: PySide6 6.8.x + cv2 DLL conflict → pin PySide6 >=6.11. (354 passed, 9 skipped).
- [x] FEAT-batch-ocr: FolderInputSource (register_as="folder"), numeric P0 chapter+image ordering, cv2 load, image_id encoding, 29 tests incl. P0 regressions. (383 passed, 9 skipped).
- [x] FEAT-single-ocr: FlatInputSource (register_as="flat"), single/list path init, numeric sort with non-numeric fallback, all chapter 1, 27 tests incl. P0 regression. (410 passed, 9 skipped).
