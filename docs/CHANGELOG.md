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
