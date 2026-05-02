# Simplified Chinese OCR Desktop App

A Windows desktop application for capturing screen regions, running OCR on Simplified Chinese text, post-processing with NLP correction and deduplication, and exporting organized chapters to EPUB format.

---

## Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| GPU | Any CUDA-capable NVIDIA | RTX 4070 Laptop (8 GB VRAM) or better |
| VRAM | 6 GB | 8 GB (`8gb` tier) or 16 GB (`16gb` tier) |
| RAM | 16 GB | 32 GB |
| OS | Windows 10 (64-bit) | Windows 11 (64-bit) |
| CUDA | 12.x | 12.6 |
| Python | 3.11 | 3.11 |

> **Note:** PaddlePaddle GPU supports CUDA up to 12.9. CUDA 13.x is not supported.

---

## Setup Instructions

### Step 1: Verify CUDA Version

```bash
nvidia-smi
```

Check the top-right corner for `CUDA Version: XX.X`. Must be 12.x. If it shows 13.x, install the CUDA 12.x runtime alongside your driver.

### Step 2: Create Conda Environment

```bash
conda create -n chinese-ocr python=3.11 -y
conda activate chinese-ocr
```

### Step 3: Install NumPy, Pillow, OpenCV via Conda

```bash
conda install -c conda-forge numpy pillow -y
conda install -c conda-forge opencv -y
```

> Use `conda-forge` OpenCV — **not** `pip install opencv-python`. The pip version bundles a Qt runtime that conflicts with PySide6 on Windows.

### Step 4: Install PySide6

```bash
pip install PySide6
```

### Step 5: Install PaddlePaddle GPU (Official Index — Not PyPI)

```bash
pip install paddlepaddle-gpu==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
```

> **Critical:** Do NOT use `uv` for this step — known wheel naming conflict. Use plain `pip` only.  
> The `cu126` index works for all CUDA 12.x sub-versions.

### Step 6: Install PaddleOCR

```bash
pip install paddleocr
pip install paddlex[ocr]
```

> `paddlex[ocr]` is required for PP-OCRv5 pipeline support. If you see `RuntimeError: A dependency error occurred during pipeline creation`, this package resolves it.

### Step 7: Install PyTorch (for MacBERT, BGE-M3, sentence-transformers)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Step 8: Install Remaining Dependencies

```bash
pip install mss ebooklib pycorrector datasketch sentence-transformers gitpython openai pynput chardet opencc-python-reimplemented jieba
```

### Step 9: Verify Environment

```bash
python scripts/verify_env.py
```

This script checks all imports, confirms GPU access, and prints a pass/fail summary.

### Step 10: Configure

```bash
cp config.example.json config.json
```

Edit `config.json`:
- Set `working_root_dir` to your session folder (e.g. `D:/ocr_sessions`)
- Set `epub_output_dir` for EPUB exports
- Add `openrouter_api_key` if using API pipeline modes
- Confirm `vram_tier` matches your GPU (`"8gb"` or `"16gb"`)

### Step 11: Run

```bash
python main.py
```

---

## Keybindings

All keybindings are configurable in `config.json` under the `keybindings` key. Default bindings:

| Action | Default Key | Description |
|---|---|---|
| **Toggle Overlay** | `F7` | Show/hide the persistent border around the capture region |
| **Reset Area** | `F8` | Open the rubber-band overlay to redefine the capture region |
| **Capture** | `F9` | Screenshot the current capture region; save to current folder |
| **New Section** | `F10` | Create the next numbered chapter folder |
| **Send to OCR** | `F11` | Run the full OCR pipeline on all captured folders |
| **Cancel** | `Escape` | Cancel the current overlay operation |

Hotkeys are **system-wide** — they work even when the app window is not focused.

---

## Pipeline Modes

| Mode | Description | Best For |
|---|---|---|
| `LOCAL_FAST` | PaddleOCR → Cleanup → Rule corrections | High-quality scans, no LLM |
| `LOCAL_STANDARD` | + MacBERT spell correction | Good balance, fully offline |
| `LOCAL_LLM` | + Ollama local LLM correction | Offline, noisy sources |
| `HYBRID_TIERED` | Routes by OCR confidence (recommended) | Mixed-quality documents |
| `API_STANDARD` | + OpenRouter LLM correction | Quality priority, API access |
| `API_FULL` | + LLM-assisted deduplication | Maximum quality |

Set `ocr_pipeline_mode` in `config.json`.

---

## VRAM Budget Notes

| Component | VRAM | Notes |
|---|---|---|
| PaddleOCR PP-OCRv5 | ~1.5 GB | Always local |
| MacBERT-base CSC | ~2 GB | Unload OCR first on 8 GB |
| BGE-M3 embeddings | ~1.1 GB | Unload after dedup phase |
| Qwen2.5-7B Q4_K_M | ~5 GB | Via Ollama; after OCR unloaded |

> **Never** load PaddleOCR + any 7B+ LLM simultaneously on 8 GB VRAM.

---

## Project Structure

```
chinese_ocr_app/
├── main.py                  # Entry point
├── config.json              # User config (gitignored)
├── config.example.json      # Example config (committed)
├── core/                    # Registry, VRAM manager, event bus
├── ocr/                     # OCR engines and post-processing stages
├── output/                  # Output formatters (EPUB, etc.)
├── input/                   # Input sources (screen capture, filesystem)
├── llm/                     # LLM provider implementations
├── gui/                     # PySide6 widgets and dialogs
├── capture/                 # Screen capture and session management
├── utils/                   # Config manager, file utils, logging
├── data/                    # Confusion tables, dictionaries
├── modules/                 # Future feature stubs (translation, manga, etc.)
├── docs/                    # Architecture guidelines and living docs
├── scripts/                 # Dev utilities (verify_env.py, etc.)
└── tests/                   # pytest test suite
```

---

## Branch Strategy

- `main` — stable builds only
- `dev` — active development
- `feature/<TICKET-ID>` — individual feature branches, merge to `dev`

---

## License

[To be determined]
