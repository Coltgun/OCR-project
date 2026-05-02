# Next Steps

## Current Status
FEAT-session-export-ui complete. 613 passed, 35 skipped. Ready for FEAT-hotkey-config (Make hotkeys configurable via SettingsDialog).

## Up Next
- [ ] FEAT-hotkey-config: Add Hotkeys tab to SettingsDialog; read hotkey bindings from config; HotkeyListener reads from config at startup
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
- [x] FEAT-dedup: MinHashDeduplicationStage (register_as="minhash_dedup"), char-bigram shingles, MinHashLSH, confidence-winner group resolution, reading-order preserved. Updated test_pipeline.py to reflect minhash_dedup now registered. (431 passed, 9 skipped).
- [x] FEAT-embedding-dedup: EmbeddingDeduplicationStage (register_as="embedding_dedup"), BGE-M3 subprocess isolation, pairwise cosine similarity, group resolution, graceful fallback on subprocess failure. 22 tests. (453 passed, 9 skipped).
- [x] FEAT-bert-correction: BertCorrectionStage (register_as="bert_correction"), MacBertCorrector subprocess isolation, text replacement with field preservation, length-mismatch + failure fallback. Updated test_pipeline.py. 23 tests. (477 passed, 9 skipped).
- [x] FEAT-llm-correction: LlmCorrectionStage (register_as="llm_correction"), Ollama local API via openai, JSON batch protocol, markdown fence stripping, per-batch fallback, partial-failure preservation. Updated test_pipeline.py. 22 tests. (500 passed, 9 skipped).
- [x] FEAT-openrouter-correction: Extracted LlmCorrectionBase (shared batch/parse/fallback logic). OpenRouterCorrectionStage (register_as="openrouter_correction") adds OpenRouter base_url, env-var API key, HTTP-Referer/X-Title headers. LlmCorrectionStage refactored to thin subclass. Updated test_pipeline.py. 19 tests. (520 passed, 9 skipped).
- [x] FEAT-hybrid-correction: HybridCorrectionStage (register_as="hybrid_correction"), confidence-tier routing (high/mid/low), delegates to bert_correction/llm_correction via _apply_stage(), merge preserves reading order, invalid-threshold fallback. Updated test_pipeline.py. 17 tests. (538 passed, 9 skipped).
- [x] FEAT-openrouter-dedup: OpenRouterDeduplicationStage (register_as="openrouter_dedup"), LLM group-assignment protocol, _request_assignments() (fence strip, range validation), _resolve_groups() confidence winner, graceful fallback. test_pipeline.py skip test upgraded to patch PIPELINE_MODES. 22 tests. (561 passed, 9 skipped).
- [x] FEAT-config-ui: SettingsDialog (4-tab QDialog: Pipeline/API Keys/VRAM/Capture), wired into MainWindow Tools menu (Ctrl+,), _open_settings slot reloads live config on accept. 6 headless tests + 13 @gui+@skip tests. (568 passed, 22 skipped).
- [x] FEAT-progress-ui: QProgressBar (200px, permanent in status bar, hidden when idle). OCR: shown on first progress(int,int) signal, value tracks done/total, hidden on results_ready or error. Export: indeterminate (0,0) during format, hidden on success or error. 10 headless + 6 @gui+@skip tests. (578 passed, 28 skipped).
- [x] FEAT-pipeline-config: OCRWorker.run() reads ocr_pipeline_mode from config, runs Pipeline(mode, config).process() on flat OCR results before emitting results_ready; unknown mode falls back to LOCAL_FAST with warning; pipeline failure falls back to raw results. 9 source-scan + 11 integration tests. (598 passed, 28 skipped).
- [x] FEAT-session-export-ui: _trigger_export persists epub_output_dir to ConfigManager after file dialog; status bar shows filename only; "Open folder" QPushButton appears in status bar after success, hidden on any state change away from IDLE; _on_open_export_folder uses os.startfile. 10 source-scan + 5 config-logic + 7 @gui+@skip tests. (613 passed, 35 skipped).
