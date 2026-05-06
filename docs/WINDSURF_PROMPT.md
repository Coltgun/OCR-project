# Windsurf Prompt — paste this into Plan Mode

You are working in the repo `Coltgun/OCR-project` on branch `dev`. The app is a Simplified-Chinese OCR tool: PySide6 GUI → mss screen capture → PaddleOCR (PP-OCRv5) → post-processing pipeline (cleanup, rule, BERT, embedding-dedup, Ollama, OpenRouter) → EPUB export. It runs on a Windows machine (Python 3.11, conda env `chinese-ocr`, RTX 4070 Laptop / 8 GB VRAM / 32 GB RAM). The functionality works end-to-end. The problem is **speed**: both the local LLM path (Ollama) and the API path (OpenRouter) are slower than expected.

I have produced an analysis package in this conversation context. Please **read these four files first** before planning:

- `IMPLEMENTATION_SPEC.md` — the ordered task plan I want you to execute.
- `PERFORMANCE_DIAGNOSIS.md` — confirmed bottlenecks with file:line evidence.
- `ACCEPTANCE_TEST_PLAN.md` — how each task is gated.
- `WINDSURF_RULES.md` — repo-specific constraints; obey strictly.

In addition, obey the existing `.windsurfrules` at the repo root. The most important standing rules are: PySide6 (not PyQt6), mss for capture, paddle and torch must NEVER co-exist in the same Python process (use subprocess isolation), numeric sort for files/folders, register stages via `register_as=`, no new pip dependencies, dev branch only, commit format `[SPEED-NN] description`.

## What I want from you in Plan Mode

1. Read the four spec files above.
2. Skim only the files listed in `IMPLEMENTATION_SPEC.md` § "Files likely to change". Do not re-explore the whole codebase.
3. Produce a numbered task plan **mirroring** the order in `IMPLEMENTATION_SPEC.md`. Don't paraphrase or expand it; just confirm the ordering, the files you'll touch per task, the rollback flag per task, and the test you'll run per task. If you spot a problem with the plan, raise it as a question — don't silently change the order.
4. Stop. Wait for my approval.

## What I want from you in Code Mode (after I approve)

For each task, in order:

1. Open a feature branch: `feature/SPEED-NN-short-name`.
2. Implement only that task. Edit in place; minimal diff.
3. Add tests per `ACCEPTANCE_TEST_PLAN.md`.
4. Run targeted tests (not the whole suite). The P0 numeric-sort test must remain green.
5. Propose a commit with message `[SPEED-NN] description`.
6. Stop and wait for review before merging or starting the next task.

Do not push. Do not open a PR. Do not skip pre-commit hooks. Do not amend across review boundaries. If a test fails, fix the root cause or stop and ask — never bypass.

## Definition of done (overall)

The package is "done" when all tasks in `IMPLEMENTATION_SPEC.md` are merged to `dev`, the success metrics in `ACCEPTANCE_TEST_PLAN.md` § E are met, and the GUI smoke test in § D passes.

## Quick anchors so you don't have to search

- OCR per-image cold-start (highest-impact bottleneck): `ocr/worker.py:74` (loop) → `ocr/worker.py:111` (`_run_single_subprocess`) → `ocr/worker.py:162` (script builder).
- LLM serial batches: `ocr/stages/llm_correction_base.py:69` (`for i in range(0, len(results), batch_size):`).
- OpenAI clients constructed per call: `ocr/stages/openrouter_correction.py:54`, `ocr/stages/openrouter_dedup.py:105`, `ocr/stages/llm_correction.py:46`.
- BERT per-call subprocess: `ocr/stages/bert_correction.py:115`.
- Embedding per-call subprocess: `ocr/stages/embedding_dedup.py:104`.
- Hybrid stage instantiates fresh sub-stages: `ocr/stages/hybrid_correction.py:130-135`.
- Pipeline assembly: `ocr/pipeline.py:142` (`_build_stages`), `pipeline.py:104` (`process`).
- Defaults: `config.example.json` (note `ocr_pipeline_mode: HYBRID_TIERED`).

## How to think about each fix

- The single biggest win is **amortising subprocess startup**. Today, every image and every BERT/embedding call pays the full cost of starting a fresh interpreter and loading the model from disk. Make the subprocess long-lived; talk to it over stdin/stdout. Keep the existing per-call subprocess as a fallback behind a config flag so we can roll back instantly.
- The second-biggest win on the API path is **concurrent batches** (`asyncio.gather` + bounded `Semaphore`) using `AsyncOpenAI`.
- All other wins (client reuse, prompt shrinking, JSON mode, result cache, skip-the-LLM gate, larger batches, hybrid-instance reuse, cuDNN warmup) are smaller but cheap.

## When you finish each task, produce

- A commit-ready summary of what changed (≤ 6 bullets).
- The benchmark numbers from `ACCEPTANCE_TEST_PLAN.md` for that task.
- The next-task plan if any blockers were discovered.

Now: read the four spec files, then enter Plan Mode and produce the task plan.
