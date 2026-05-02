# Story Memory Module (Future)

Per-story vector store + LLM memory for translation consistency.

## Planned features
- BGE-M3 embedding-based term lookup (fuzzy match for inflected/variant forms)
- SQLite-backed persistent term store per story_id
- Rolling context window for recent paragraphs (feed to LLM as few-shot examples)
- Glossary export/import (JSON, TSV)

## Status
**Stub only.** Do not implement until story_memory module is formally scoped.
