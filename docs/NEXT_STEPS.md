# Next Steps

## Current Status
ENV-001 complete. chinese-ocr env verified. Ready for FEAT-capture (Phase 1).

## Up Next
- [ ] FEAT-capture: Screen capture pipeline (mss, session folders, hotkeys, state machine)
## Completed
- [x] ARCH-001: Core Registry System — core/registry.py, core/vram_manager.py, core/event_bus.py (58 tests passing)
- [x] ARCH-002: Define All ABCs — OCREngine, PostProcessStage, OutputFormatter, InputSource, LLMProvider + 4 module stubs (77 tests passing)
- [x] ARCH-003: VRAM Tier Configuration — ConfigManager, file_utils, logging_config, confusion_table.json, init_from_config() (135 tests passing)
- [x] ENV-001: chinese-ocr conda env created (Python 3.11.15), all packages verified. Architecture constraint documented: torch+paddle must not share a process (cuDNN DLL conflict).
