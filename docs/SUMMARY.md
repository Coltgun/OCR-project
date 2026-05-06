# OCR Speed Optimization Package — Executive Summary

## Repo under analysis
`Coltgun/OCR-project` @ branch `dev` (commit `d946e50`). Python 3.11, PySide6 GUI, PaddleOCR PP-OCRv5, Ollama (local LLM) and OpenRouter (API LLM) post-processing, plus MacBERT and BGE-M3 stages run via subprocess for paddle/torch DLL isolation.

## What this package contains

| File | Purpose |
|---|---|
| `WINDSURF_PROMPT.md` | Paste-ready prompt for Windsurf Plan→Code mode. Self-contained. |
| `IMPLEMENTATION_SPEC.md` | Exact refactor design, files to touch, ordered tasks, rollback, flags. |
| `PERFORMANCE_DIAGNOSIS.md` | Evidence-based slowdown causes (confirmed vs. hypothesis). |
| `ACCEPTANCE_TEST_PLAN.md` | Benchmarks, regression tests, manual checks, success metrics. |
| `WINDSURF_RULES.md` | Project-specific rules to prevent breakage and minimize tokens. |

## Headline findings (confirmed in code)

1. **Per-image PaddleOCR cold start.** `ocr/worker.py:111` spawns a fresh Python subprocess **per image**, re-importing `paddle` + `paddleocr`, re-loading detection + recognition + orientation models, and re-registering CUDA DLL dirs every time. Cold-start cost ≈ 8–25 s on Windows + RTX 4070; recognition itself is ~50–200 ms/image. For an N-image batch the worker pays N× cold start instead of 1×.
2. **LLM correction is strictly sequential per batch.** `ocr/stages/llm_correction_base.py:69` iterates `range(0, len(results), batch_size)` and awaits each `chat.completions.create` call serially. With Ollama (local), the model is single-stream so concurrency is bounded, but the API path (OpenRouter) is round-trip-bound and trivially parallelizable.
3. **OpenAI clients are recreated per `process()` call** with default `httpx` connection pool, no `max_retries` tuning, no session reuse across stages. `openrouter_correction.py:54` and `openrouter_dedup.py:105`.
4. **No prompt caching, no result memoization.** Identical OCR lines (extremely common: chapter headers, repeated speaker tags) round-trip to the LLM every run. The system prompt (~250 chars Chinese) is re-sent on every batch.
5. **Embedding dedup spawns a torch subprocess that loads BGE-M3 (~1.1 GB) from scratch every call** (`ocr/stages/embedding_dedup.py:141`). Same for MacBERT in `bert_correction.py:150`. With session-level state these should load once and stay resident (subject to VRAM tier).
6. **`hybrid_correction` instantiates Bert and LLM stage classes inside `_apply_stage`** for each call (`hybrid_correction.py:134`), and Bert/LLM each spawn their own subprocess — so a single hybrid run can cost 2 cold subprocess starts.
7. **HYBRID_TIERED is the default** (`config.example.json:21`) but BERT inside it uses `bert_batch_size=32` and a 5-min subprocess timeout — most of the time per call is model-load, not inference.
8. **No streaming, no async I/O, no concurrent LLM batches**; default batch size (10) is small for cheap API models.

## Top wins (ordered by impact / risk ratio)

| # | Change | Est. wall-clock impact | Risk |
|---|---|---|---|
| 1 | Long-lived **OCR subprocess** that processes a queue of images (1× model load per session) | 5–20× speedup on multi-image OCR | Medium (IPC) |
| 2 | Long-lived **BERT/embedding subprocess** with stdin/stdout JSON-line protocol | 3–10× on bert/embedding stages | Medium |
| 3 | **Concurrent LLM batches** for OpenRouter via `asyncio` + `AsyncOpenAI`, configurable `max_concurrency` | 3–8× on API path | Low–Medium |
| 4 | **Module-level OpenAI client** with reused `httpx.Client`, tuned timeouts/retries | 5–15% per batch | Low |
| 5 | **In-memory + on-disk LRU cache** keyed by hash(text+model+stage) for LLM corrections | Variable; large for re-runs | Low |
| 6 | **Shrink system prompt** + use **JSON mode / response_format** when supported; tighten user payload | 10–30% token reduction | Low |
| 7 | **Skip LLM call for short or already-clean lines** (heuristic gate before LLM) | 20–50% fewer calls | Low |
| 8 | **Increase batch_size** for cheap models; set per-provider defaults | 1.5–3× | Low |
| 9 | **Streaming** for OpenRouter when latency-bound UI feedback is desired (optional) | Perceived only | Low |
| 10 | **Add timing instrumentation** (per-stage, per-batch) and a `--profile` mode | Diagnosis only | None |

## How to use

1. Open Windsurf in this repo, switch to **Plan Mode**.
2. Paste the contents of `WINDSURF_PROMPT.md`.
3. Attach the four reference docs (`IMPLEMENTATION_SPEC.md`, `PERFORMANCE_DIAGNOSIS.md`, `ACCEPTANCE_TEST_PLAN.md`, `WINDSURF_RULES.md`) so they're in context.
4. Approve the plan. Proceed to **Code Mode** task by task in the order listed in `IMPLEMENTATION_SPEC.md`.
5. Gate each task on the corresponding bench in `ACCEPTANCE_TEST_PLAN.md` before merging.

## Safe-default principles

- All optimizations are **gated behind config flags** so you can A/B and roll back per stage.
- **No public interface changes** to `OCRResult`, `OCREngine`, `PostProcessStage`, `Pipeline.process`.
- **No removal of subprocess isolation** — only its frequency. Paddle/torch DLL conflict still respected.
- The existing **subprocess fallback paths remain** as safety net.
