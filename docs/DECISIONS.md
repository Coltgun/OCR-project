# Architecture Decisions

Record decisions here as they are made. Format: decision, rationale, date.

## Registry Pattern: __init_subclass__ over entry_points
Using Python's `__init_subclass__` hook for auto-registration. No external framework, works at import time, zero config files. See app_guidelines.md Section 11.2.

## Registry Keyword: register_as= instead of name=
**Date:** 2026-05-02  
`ABCMeta.__new__()` already uses `name` as its own parameter (the class name). Passing `name=` as a class keyword argument causes `TypeError: multiple values for argument 'name'` on Python 3.10+. The registration keyword is `register_as=` instead.  
Example: `class PaddleOCREngine(OCREngine, register_as="paddleocr"): ...`
