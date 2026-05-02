# Changelog

All notable changes to this project follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added — 2026-05-02
- **ARCH-001** `core/registry.py` — `Registrable` base with `__init_subclass__` auto-registration. Registration keyword is `register_as=` (not `name=`, which conflicts with `ABCMeta`).
- **ARCH-001** `core/vram_manager.py` — `VRAMManager` with `allocate`/`release`/`can_allocate`; `make_vram_manager(config)` factory; tier defaults 7680 MB (8 GB) / 15360 MB (16 GB).
- **ARCH-001** `core/event_bus.py` — `EventBus` with `subscribe`/`unsubscribe`/`publish`/`clear`; exception isolation per subscriber.
- `tests/core/test_registry.py`, `test_vram_manager.py`, `test_event_bus.py` — 58 tests, all passing.
- **ARCH-002** `core/types.py` — `BoundingBox`, `OCRResult`, `Chapter` shared dataclasses.
- **ARCH-002** `ocr/engines/base.py` — `OCREngine(Registrable)` ABC.
- **ARCH-002** `ocr/stages/base.py` — `PostProcessStage(Registrable)` ABC.
- **ARCH-002** `output/base.py` — `OutputFormatter(Registrable)` ABC.
- **ARCH-002** `input/base.py` — `InputSource(Registrable)` ABC.
- **ARCH-002** `llm/base.py` — `LLMProvider(Registrable)` ABC.
- **ARCH-002** `modules/translation/`, `manga/`, `web_scraper/`, `story_memory/` — future feature stubs with ABCs and READMEs.
- `tests/core/test_abcs.py` — 19 tests covering all ABCs and data types (77 total passing).
- **ARCH-003** `utils/config_manager.py` — `ConfigManager` dotted-key get/set/save/load with atomic write; module-level singleton.
- **ARCH-003** `utils/file_utils.py` — `sort_folders_numeric`, `sort_images_numeric`, `sort_image_paths_numeric`, `sort_folder_paths_numeric`, `discover_images`, `discover_chapter_folders`, `next_image_path`.
- **ARCH-003** `utils/logging_config.py` — `setup_logging()` with rotating file + console handlers.
- **ARCH-003** `core/vram_manager.py` — added `init_from_config()` to re-initialise singleton from config at startup.
- **ARCH-003** `data/confusion_table.json` — initial Chinese OCR confusion pairs.
- **ARCH-003** `data/ocr_dictionary.json` — empty dictionary (future use).
- `tests/utils/test_file_utils.py`, `test_config_manager.py` — 56 tests; P0 `test_numeric_sort_never_lexicographic` present (135 total passing).
- **ENV-001** `chinese-ocr` conda env created with Python 3.11.15, all packages verified via `scripts/verify_env.py` (all OK).
- **ENV-001** `utils/cuda_utils.py` — `register_nvidia_dll_dirs()` for Windows DLL path fix before paddle import.
- **ENV-001** `environment.yml` generated from verified env state.
- **ENV-001** `docs/KNOWN_ISSUES.md` — torch+paddle cuDNN DLL conflict documented; process isolation constraint added to DECISIONS.md.
- **ENV-001** `scripts/verify_env.py` — subprocess isolation for paddle/paddleocr checks; OSError caught; PADDLE_PACKAGES list.
- **FEAT-capture** `capture/session.py` — `CaptureSession`: folder counter dict, `get_next_image_path()`, `new_section()`, `resume_from_disk()`, `validate_session_name()`.
- **FEAT-capture** `capture/state.py` — `AppState` enum, `StateMachine(QObject)` with `state_changed` signal; valid transition table; invalid transitions silently ignored.
- **FEAT-capture** `capture/hotkeys.py` — `HotkeyListener(QObject)`: pynput daemon thread, Qt signal bridge, configurable keybindings from config dict.
- **FEAT-capture** `capture/screen_capture.py` — `ScreenCapture`: mss grab, `apply_rotation()` (none/90cw/90ccw/180/auto), auto heuristic (aspect ratio + Hough fallback), mss injection for tests.
- **FEAT-capture** `gui/overlay.py` — `CaptureOverlay` (rubber-band QRubberBand selector), `RegionBorderOverlay` (WindowTransparentForInput persistent border).
- `tests/capture/` — 80 new tests (session, state machine, screen_capture); P0 numeric sort tests for resume and counter init. (215 total passing).
- **FEAT-ocr-engine** `ocr/engines/paddle_engine.py` — `PaddleOCREngine(register_as="paddleocr")`: initialize/recognize/unload, VRAM alloc/release, PP-OCRv5 result parsing, quad_to_bbox, updated API (device=, use_textline_orientation).
- **FEAT-ocr-engine** `ocr/worker.py` — `OCRWorker(QRunnable)`: subprocess-per-image OCR dispatch, `OCRWorkerSignals` (results_ready, error_occurred, progress), JSON result serialisation.
- `tests/ocr/test_paddle_engine.py` — 22 tests: registry, VRAM lifecycle, parse_results, quad_to_bbox, recognize output; all mocked (no real GPU). (237 total passing).
- **FEAT-pipeline** `ocr/stages/cleanup.py` — `CleanupStage(register_as="cleanup")`: NFC normalization, fullwidth→halfwidth (alphanum only, Chinese punctuation preserved), CJK space removal, punctuation normalization, garbage filtering (confidence threshold, CJK ratio, repeated chars).
- **FEAT-pipeline** `ocr/stages/rule_corrections.py` — `RuleCorrectionsStage(register_as="rule_corrections")`: confusion table JSON load + reverse lookup, character substitution, decimal-point pattern fix, lazy load + reload_tables().
- **FEAT-pipeline** `ocr/pipeline.py` — `Pipeline` orchestrator: `PIPELINE_MODES` dict (6 modes), `process()`, unregistered stages skipped gracefully, stage exception isolation.
- `tests/ocr/test_cleanup.py`, `test_rule_corrections.py`, `test_pipeline.py` — 81 new tests. (318 total passing).
