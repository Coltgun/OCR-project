# Windsurf Rules — Repo-Specific

These rules supplement the existing `.windsurfrules` file. They are scoped to this optimization work and exist to (a) prevent breaking working behavior, (b) minimize Windsurf token/compute cost, and (c) preserve public interfaces.

## Stop conditions — abort and surface to the user

Stop and ask before:
- Removing any subprocess isolation (paddle/torch must stay in different processes).
- Changing the signature of `OCRWorker`, `Pipeline`, `PostProcessStage`, `OCREngine`, or any dataclass in `core/types.py`.
- Adding a new pip/conda dependency. The plan explicitly avoids this.
- Modifying anything under `modules/` (stubs only per `.windsurfrules`).
- Touching the EPUB chapter ordering / numeric-sort code paths.
- Disabling or weakening the parsers in `ocr/stages/llm_correction_base.py:_parse_response`.
- Bumping default batch sizes beyond the values listed in `IMPLEMENTATION_SPEC.md` Task 10.
- Replacing `mss` for capture or `PySide6` for GUI.

## Token-frugal coding rules

1. **Edit in place.** Do not rewrite unchanged sections of files. Use minimal-diff edits.
2. **No big rewrites of `_build_subprocess_script`** in `worker.py`/`bert_correction.py`/`embedding_dedup.py`. Extract the new subprocess script into its own file (`worker_subprocess.py`, `_bert_subprocess.py`, `_embedding_subprocess.py`) so future edits don't churn the parent file.
3. **One task per commit.** Commit messages: `[SPEED-NN] short description`.
4. **Don't re-read the whole repo each task.** The relevant files are listed in `IMPLEMENTATION_SPEC.md`. Read only those.
5. **Don't generate large illustrative blocks.** Inline only the snippets you need to write the code; reference `PERFORMANCE_DIAGNOSIS.md` for context.
6. **Don't run all of pytest after a one-line change.** Run the targeted module(s).

## Interface-preservation rules

- `OCRResult` field order, names, and types are frozen. `dataclasses.replace` is the only legal way to mutate.
- `Pipeline.process(results: list[OCRResult]) -> list[OCRResult]` signature is frozen.
- Stage `register_as=` keys are frozen; don't rename them — they're load-bearing for `PIPELINE_MODES`.
- `OCRWorkerSignals` (`results_ready`, `error_occurred`, `progress`) is frozen — the GUI is wired directly to these names.
- `BoundingBox` and `Chapter` are frozen.

## Behavior-preservation rules

- The fallback paths in `_run_subprocess` (Bert / Embedding) and `_run_single_subprocess` (OCR) must remain reachable via config flag.
- The 3-strategy `_parse_response` parser must remain. Don't remove fallbacks even if you add JSON mode.
- The "keep originals on any error" semantics in LLM stages must remain intact for both sync and async paths.
- Numeric sort everywhere (`sorted(items, key=lambda x: int(x.stem))`).

## Concurrency rules

- **Ollama default concurrency = 1.** Local serialization is by design (single-GPU, single-stream).
- **OpenRouter concurrency capped at 8** in defaults; users can raise. Add per-account RPM awareness if Windsurf adds a knob.
- **Async path must not import torch.** Async only applies to LLM/HTTP stages.
- **Never mix `asyncio.run` with the running Qt event loop.** The pipeline runs in a `QRunnable` worker thread — `asyncio.run` is safe there.

## Cache rules

- Cache **only correction**, **not dedup** (dedup output depends on the entire batch).
- Cache key includes `system_prompt` digest so prompt changes invalidate.
- Disk cache file is JSON under `working_root_dir`. Atomic writes (write to `.tmp`, rename).
- Cache eviction: simple FIFO at `llm_result_cache_max_entries`.

## Logging rules

- Use `utils/logging_config.py` only (no `print` for ops).
- Wrap hot-path debug logs with `if logger.isEnabledFor(logging.DEBUG):`.
- New `[PERF]` log lines should be prefixed exactly so that bench scripts can grep them.

## Testing rules

- Add a unit test for every new module.
- For subprocess services, mock `subprocess.Popen` at the boundary; do not start real children in unit tests (start them in an integration test marked `@pytest.mark.slow`).
- Re-run `pytest tests/utils/test_file_utils.py::test_numeric_sort_never_lexicographic` after any pipeline change (P0 per `.windsurfrules`).
- **Don't mark slow tests as required for CI** unless tagged.

## Config rules

- All new flags get an entry in `config.example.json` with safe defaults.
- Defaults must preserve current behavior unless the change is functional fix (e.g., bigger batch sizes are a tuning improvement; gate them or document the change).
- Use `utils/config_manager.py` dotted-key access — never `json.load(open(...))` directly (per `.windsurfrules`).

## Plan-mode etiquette (Windsurf-specific)

- **Plan mode**: produce a numbered task plan that mirrors `IMPLEMENTATION_SPEC.md`. Don't restate the whole file — reference it.
- **Code mode**: implement one task at a time. After each task, propose a commit message and stop for review.
- **Don't open a PR**. The user runs the Source Control panel.
- **Don't call `git push`**. Local commits only unless the user requests otherwise.
- If a test fails, **don't `--no-verify`**. Fix the underlying issue or stop and ask.

## Forbidden actions

- ❌ Don't replace `subprocess` with `multiprocessing` (DLL isolation requires fresh interpreter on Windows).
- ❌ Don't import `torch` or `paddle` in the main GUI process. Ever.
- ❌ Don't add `pyautogui`, `PIL.ImageGrab`, `PyQt6`, or `opencv-python` (pip).
- ❌ Don't sort by string for chapter / image / folder ordering.
- ❌ Don't hardcode model names — read from config (per `.windsurfrules`).
- ❌ Don't store `OPENROUTER_API_KEY` in any file except `config.json` (gitignored) or `.env`.
- ❌ Don't write large explanatory docstrings in production files for these tasks; the spec docs cover that.

## When in doubt

If a change conflicts with these rules or with `.windsurfrules`, **stop and ask** rather than guess. The cost of a clarifying question is much lower than the cost of breaking working behavior.
