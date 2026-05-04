# Installation Guide — Simplified Chinese OCR App

Windows-only. Requires an NVIDIA GPU with CUDA 12.x.

---

## What You Need to Install Manually First

These must be in place **before** running `install.ps1`.
The installer cannot handle them automatically.

| Prerequisite | Why | Where to get it |
|---|---|---|
| **NVIDIA GPU driver** | Needed for CUDA | [nvidia.com/Download](https://www.nvidia.com/Download/index.aspx) |
| **CUDA 12.x Toolkit** | PaddlePaddle GPU requires ≤12.9 | [CUDA 12.6 archive](https://developer.nvidia.com/cuda-12-6-0-download-archive) |
| **Git** | To clone this repository | [git-scm.com](https://git-scm.com/download/win) |

> **CUDA version check:** Run `nvidia-smi` in a terminal. The top-right corner shows `CUDA Version: X.X`.
> If it shows 13.x, install the CUDA 12.6 Toolkit alongside your existing driver.

---

## Quick Install (3 steps)

### 1. Clone the repository

```powershell
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

### 2. Run the installer

Right-click PowerShell → "Run as Administrator" (or set execution policy first):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\install.ps1
```

The installer will:
- Auto-download and install **Miniconda3** if `conda` is not found
- Create the `chinese-ocr` conda environment (Python 3.11)
- Install all packages in the correct order (conda-forge → PaddlePaddle → PyTorch → pip)
- Install **opencv headless** (no Qt6 GUI build) — avoids a Qt DLL conflict with PySide6
- Install **PySide6 6.8.3** (pinned — this version bundles its own ICU DLLs, required on Windows)
- Optionally install **Ollama** (prompts you — needed only for LLM pipeline modes)
- Copy `config.example.json` → `config.json` if it doesn't exist
- Run `scripts/verify_env.py` and print a PASS/FAIL summary

### 3. Configure

Open `config.json` and set at minimum:

| Key | Description | Example |
|---|---|---|
| `working_root_dir` | Where session folders are saved | `"D:/ocr_sessions"` |
| `epub_output_dir` | Where EPUB files are exported | `"D:/ocr_sessions/epub_output"` |
| `vram_tier` | Match your GPU VRAM | `"8gb"` or `"16gb"` |
| `openrouter_api_key` | Only for API_STANDARD / API_FULL modes | `"sk-or-..."` |

---

## Running the App

| Method | How |
|---|---|
| **Easiest** | Double-click `run.bat` |
| **PowerShell** | `.\run.ps1` |
| **Desktop shortcut** | Run `make_shortcut.bat` once, then double-click the icon |
| **Manual** | `conda activate chinese-ocr` then `python main.py` |

---

## LLM Pipeline Modes (Optional)

To use `LOCAL_LLM` or `HYBRID_TIERED` modes you need **Ollama** with a model loaded:

```powershell
# Install Ollama (if skipped during install.ps1)
# https://ollama.com

# Pull the default model (~5 GB download)
ollama pull qwen2.5:7b-instruct-q4_K_M
```

Then set `"ocr_pipeline_mode": "HYBRID_TIERED"` in `config.json` or via the Settings dialog.

For `API_STANDARD` / `API_FULL` modes, set `openrouter_api_key` in `config.json`.
Get a key at [openrouter.ai](https://openrouter.ai).

---

## VRAM Budget Reference

| Component | VRAM | Notes |
|---|---|---|
| PaddleOCR PP-OCRv5 | ~1.5 GB | Always local |
| MacBERT-base CSC | ~2 GB | Unload OCR first on 8 GB tier |
| BGE-M3 embeddings | ~1.1 GB | Unload after dedup phase |
| Qwen2.5-7B Q4_K_M | ~5 GB | Via Ollama; OCR must be unloaded first |

> **8 GB GPU:** Do NOT load PaddleOCR and any 7B+ LLM at the same time.
> The app manages this automatically via the VRAM tier setting.

---

## Troubleshooting

**`conda` not found after install:**
Close and reopen PowerShell (Miniconda adds itself to PATH on next shell launch).

**`DLL load failed while importing QtWidgets` / `WinError 127`:**
This means PySide6 is the wrong version or there is a Qt DLL conflict.
Fix: ensure PySide6 6.8.3 is installed and conda-forge `qt6-main` is not present:
```powershell
conda run -n chinese-ocr pip install PySide6==6.8.3
conda remove -n chinese-ocr qt6-main --force -y   # only if present
```

**numpy crash (`blas_fpe_check` / `fatal exception 0xc06d007f`):**
The pip numpy build conflicts with conda-forge MKL. Fix:
```powershell
conda run -n chinese-ocr pip uninstall numpy -y
conda install -n chinese-ocr -c conda-forge "numpy>=2.0,<2.3" -y
```

**PaddlePaddle import error / DLL conflict:**
PaddlePaddle GPU and PyTorch bundle incompatible cuDNN versions. The app runs them
in separate subprocesses to avoid this — do not import both in the same Python script.

**App won't start / missing `config.json`:**
Run `copy config.example.json config.json` and edit the paths.

**Verify the environment manually:**
```powershell
conda activate chinese-ocr
python scripts/verify_env.py
```
