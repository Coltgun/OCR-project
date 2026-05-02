# Architecture Decisions

Record decisions here as they are made. Format: decision, rationale, date.

## Registry Pattern: __init_subclass__ over entry_points
Using Python's `__init_subclass__` hook for auto-registration. No external framework, works at import time, zero config files. See app_guidelines.md Section 11.2.

## torch and paddle must run in separate processes
**Date:** 2026-05-02  
`torch` (cu121) and `paddlepaddle-gpu` (cu126) bundle incompatible cuDNN 9 DLL builds. They cannot coexist in the same Windows process (`WinError 127`). OCR pipeline stages (paddle) run in the main process; torch-based stages (MacBERT, BGE-M3) must run in a subprocess or worker process. See `KNOWN_ISSUES.md` for full details.

## Registry Keyword: register_as= instead of name=
**Date:** 2026-05-02  
`ABCMeta.__new__()` already uses `name` as its own parameter (the class name). Passing `name=` as a class keyword argument causes `TypeError: multiple values for argument 'name'` on Python 3.10+. The registration keyword is `register_as=` instead.  
Example: `class PaddleOCREngine(OCREngine, register_as="paddleocr"): ...`
