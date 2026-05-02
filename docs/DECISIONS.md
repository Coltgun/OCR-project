# Architecture Decisions

Record decisions here as they are made. Format: decision, rationale, date.

## Registry Pattern: __init_subclass__ over entry_points
Using Python's `__init_subclass__` hook for auto-registration. No external framework, works at import time, zero config files. See app_guidelines.md Section 11.2.
