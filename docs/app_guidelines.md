# Simplified Chinese OCR App — Architecture & Design Guidelines

**Target Hardware:** Windows laptop, RTX 4070 (8 GB VRAM), i7-13700HX, 32 GB RAM  
**Primary Use Case:** Capture manga/novel reader regions from screen, OCR the text, post-process, and export to EPUB organized by chapters.

---

## 1. Architecture Overview

### Three Major Modes

| Mode | Description |
|---|---|
| **Capture Mode** | Live session: user presses hotkeys to screenshot a defined region, organizes shots into numbered chapter folders, then triggers OCR on the whole batch. |
| **Batch OCR Mode** | No capture: user points the app at an existing folder tree (subfolders = chapters, images inside), runs the full OCR pipeline on all images. |
| **Single OCR Mode** | No capture: user selects one image or a flat list of images, runs OCR, gets immediate output without chapter organization. |

### GUI Framework

Use **PySide6** (LGPL license). Do **not** use PyQt6 — PyQt6 uses a GPL/commercial dual license that creates friction for any downstream commercial use. PySide6 and PyQt6 share the same Qt6 API surface, so all documentation and examples are directly transferable. PySide6 supports both `.ui` file loading via `QUiLoader` and fully code-defined widget trees.

```python
# PySide6 imports follow this pattern:
from PySide6.QtWidgets import QApplication, QMainWindow, QRubberBand
from PySide6.QtCore import Qt, QRect, QSize, Signal, Slot
from PySide6.QtGui import QPainter, QColor
```

### Screen Capture

Use **mss** for all screen capture operations. `mss` is 30–45× faster than `pyautogui` or PIL's `ImageGrab` for region capture, with measured latency of approximately 45–65 ms per screenshot on Windows. It handles multi-monitor setups correctly and returns numpy-compatible arrays.

```python
import mss
import mss.tools

with mss.mss() as sct:
    monitor = {"top": y, "left": x, "width": w, "height": h}
    sct_img = sct.grab(monitor)
    # Convert to PIL Image or numpy array as needed
```

### Overlay / Rubber-Band Selection

The capture region selector is a full-screen, transparent, frameless window using PySide6 `QRubberBand`. Standard pattern:

```python
class CaptureOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.showFullScreen()
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.origin = QPoint()

    def mousePressEvent(self, event):
        self.origin = event.position().toPoint()
        self.rubber_band.setGeometry(QRect(self.origin, QSize()))
        self.rubber_band.show()

    def mouseMoveEvent(self, event):
        self.rubber_band.setGeometry(
            QRect(self.origin, event.position().toPoint()).normalized()
        )

    def mouseReleaseEvent(self, event):
        region = QRect(self.origin, event.position().toPoint()).normalized()
        self.region_selected.emit(region)
        self.close()
```

This is the correct, standard approach for cross-screen overlay capture selectors on Windows with Qt6. Do not use platform-specific Win32 APIs.

### State Machine

The app runs a well-defined state machine to prevent race conditions between hotkey events, GUI actions, and background pipeline tasks.

```
IDLE
 ├──[F8 / Reset Area]──→ SELECTING
 │                           └──[drag complete / Escape]──→ IDLE
 ├──[F9 / Capture]──→ CAPTURING
 │                        └──[done / error]──→ IDLE
 ├──[F11 / Send to OCR]──→ OCR_RUNNING
 │                              └──[done / cancel / error]──→ IDLE
 └──[Export triggered]──→ EXPORTING
                              └──[done / error]──→ IDLE
```

- Only one non-IDLE state is active at a time.
- Hotkeys that would trigger invalid state transitions are silently ignored (e.g., F9 while OCR_RUNNING).
- State transitions emit Qt signals; the main window connects to these signals to update UI elements (status bar, button states, overlay visibility).

---

## 2. Capture Pipeline — Detailed Specification

### Session Initialization

On every app startup (or when "New Session" is selected from the menu):

1. Show a dialog asking for a **working folder name**.
2. Validate: must be a non-empty string of digits only. Reject anything non-numeric with an inline error message. Acceptable: `001`, `42`, `007`. Rejected: `chapter1`, `test`, ``.
3. The validated name becomes the root subfolder under `working_root_dir` from config. Example: `working_root_dir = D:/ocr_sessions`, working folder = `003` → session root = `D:/ocr_sessions/003/`.
4. If the folder already exists, ask the user whether to resume (appending to existing numbered subfolders) or overwrite (delete and restart). Default: resume.

### Folder and File Naming — Critical Correctness Requirement

> **This is a P0 correctness requirement. Violating it produces silently wrong EPUB chapter order.**

All folder names within a session are **plain integers** without zero-padding: `1`, `2`, `3`, ..., `10`, `11`, etc.

All image files within a folder use **zero-padded integers** with 4 digits: `0001.png`, `0002.png`, ..., `9999.png`.

**Sorting MUST always use numeric sort, never lexicographic sort:**

```python
# CORRECT — always do this:
sorted_folders = sorted(folder_names, key=lambda x: int(x))
sorted_images = sorted(image_names, key=lambda x: int(x.stem))

# WRONG — never do this:
sorted_folders = sorted(folder_names)          # '1','10','2' order
sorted_folders = glob.glob("*/")               # filesystem order, undefined
sorted_folders = os.listdir(session_root)      # undefined order
```

The only safe pattern is explicit `key=lambda x: int(x)` on folder names. Whenever any code path reads folder lists or image lists from disk, it MUST apply this sort. This includes: EPUB assembly, OCR batch dispatch, progress display, git commit message generation.

**Unit tests MUST cover the ordering bug.** See Section 10.

### Image Counter Management

Each session maintains an in-memory dictionary mapping folder number → current image counter:

```python
# In session.py
self.folder_counters: dict[int, int] = {}

def get_next_image_path(self, folder_num: int) -> Path:
    if folder_num not in self.folder_counters:
        # Scan existing images in folder to resume correctly
        existing = sorted(
            [int(p.stem) for p in self.folder_path(folder_num).glob("*.png")]
        )
        self.folder_counters[folder_num] = existing[-1] if existing else 0
    self.folder_counters[folder_num] += 1
    filename = f"{self.folder_counters[folder_num]:04d}.png"
    return self.folder_path(folder_num) / filename
```

This correctly handles resuming a session that already has images on disk.

### Keybindings

All keybindings are configurable and stored in `config.json` under the `keybindings` key. Defaults:

| Action | Default Key | Description |
|---|---|---|
| Capture | `F9` | Screenshot the current capture region; save to current folder |
| New Section | `F10` | Create the next numbered folder; increment section counter |
| Send to OCR | `F11` | Run the full OCR pipeline on all captured folders |
| Reset Area | `F8` | Open the rubber-band overlay to redefine the capture region |
| Toggle Overlay | `F7` | Show/hide the persistent border overlay around the capture area |
| Cancel | `Escape` | Cancel the current overlay operation (selecting, etc.) |

Hotkey listening is system-wide (works when the app is not focused) using **pynput**:

```python
from pynput import keyboard

def on_press(key):
    try:
        # Map pynput key objects to action names
        if key == keyboard.Key.f9:
            app_state.trigger_capture()
        elif key == keyboard.Key.f10:
            app_state.trigger_new_section()
        # ... etc
    except Exception:
        pass  # Never crash the listener thread

listener = keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()
```

`pynput` is preferred over the `keyboard` library because `keyboard` requires Administrator privileges on some Windows configurations, while `pynput` works in user space.

### Fine Adjustment Panel

After a rubber-band drag completes and emits the initial region, show a fine-adjustment panel (a small non-blocking `QDialog` or docked widget) containing:

- Four `QSpinBox` widgets: X, Y, Width, Height
- Pre-populated with the values from the rubber-band drag result
- Ranges: X/Y: 0 to monitor width/height; Width/Height: 1 to monitor width/height
- A live preview: whenever any spinbox changes, immediately update the persistent border overlay (Section 2, Overlay Border below) to reflect the new values. The user sees the border move/resize in real time as they adjust spinboxes.
- Confirm and Cancel buttons. Confirm stores the region to config and to in-memory state.

### Auto-Rotate Options

Configured at startup dialog or in the Settings dialog. Stored as `rotation_mode` in config.

**Fixed rotation modes:** `none`, `90cw`, `90ccw`, `180`. Applied uniformly to all captured images before saving. Use `PIL.Image.rotate()` or `cv2.rotate()`.

**Auto-detect mode** (when `rotation_mode == "auto"`):

1. **Step 1 — Aspect ratio heuristic (fastest, <5 ms):**
   - If `width > height * 1.3`: image is landscape → rotate 90° CW to portrait
   - If `height > width * 1.3`: image is already portrait → no rotation
   - If neither condition holds (roughly square): proceed to Step 2

2. **Step 2 — Hough line / text baseline angle (only when aspect ratio is ambiguous, <50 ms target):**
   ```python
   import cv2
   import numpy as np

   def detect_rotation_angle(img_gray: np.ndarray) -> float:
       edges = cv2.Canny(img_gray, 50, 150, apertureSize=3)
       lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80,
                               minLineLength=50, maxLineGap=10)
       if lines is None or len(lines) == 0:
           return 0.0
       angles = []
       for line in lines:
           x1, y1, x2, y2 = line[0]
           angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
           angles.append(angle)
       median_angle = np.median(angles)
       # Snap to nearest 90° increment if close enough
       for snap in [-90, 0, 90, 180]:
           if abs(median_angle - snap) < 15:
               return snap
       return median_angle

   def correct_rotation(image: np.ndarray, angle: float) -> np.ndarray:
       if angle == 0:
           return image
       h, w = image.shape[:2]
       center = (w // 2, h // 2)
       M = cv2.getRotationMatrix2D(center, -angle, 1.0)
       return cv2.warpAffine(image, M, (w, h),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)
   ```

3. **Portrait vs. landscape orientation disambiguation**: Use PaddleOCR text bounding box orientation — if the majority of detected text boxes have `height > width * 2`, the text is vertical (common in traditional Chinese layout); if `width > height`, text is horizontal. This confirms or overrides the aspect ratio decision.

Do **not** use a neural network classifier for rotation detection. The heuristic + Hough approach must complete in under 50 ms per image on the target hardware. Neural classifiers add 200–500 ms and are unnecessary for this use case.

### Overlay Border (Capture Region Indicator)

A persistent, always-on-top, non-interactive window that draws a colored rectangle around the current capture region. Visibility is toggled with F7.

```python
class RegionBorderOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput  # non-interactive
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.border_color = QColor(255, 100, 0, 200)  # Orange, semi-transparent
        self.border_width = 3

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(self.border_color, self.border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

    def update_region(self, x: int, y: int, w: int, h: int):
        self.setGeometry(x, y, w, h)
        self.update()
```

`Qt.WindowType.WindowTransparentForInput` ensures all mouse events pass through to the window underneath. The overlay is geometry-positioned to exactly match the capture region.

---

## 3. OCR Pipeline — Modes

### PaddleOCR Initialization (Shared by All Modes)

```python
from paddleocr import PaddleOCR

class OCREngine:
    _instance: PaddleOCR | None = None

    def get_engine(self) -> PaddleOCR:
        if self._instance is None:
            self._instance = PaddleOCR(
                use_angle_cls=True,
                lang='ch',
                use_gpu=config.paddleocr_use_gpu,
                show_log=False,
            )
        return self._instance

    def unload(self):
        """Explicitly unload to free VRAM before loading PyTorch models."""
        self._instance = None
        import paddle
        paddle.device.cuda.empty_cache()
```

**Model lifecycle note:** PaddleOCR and PyTorch-based models (MacBERT, BGE-M3, sentence-transformers) **cannot both be fully loaded simultaneously** on an 8 GB VRAM card without risking OOM errors. Always call `engine.unload()` before loading a PyTorch model, and vice versa. See Section 9 for the full VRAM budget discussion.

### Stage Definitions

| Stage | Name | Description |
|---|---|---|
| Stage 1 | Cleanup | Remove OCR artifacts: stray punctuation, repeated chars, whitespace normalization, invalid Unicode, split/merge obvious errors |
| Stage 2A | Rule Corrections | Dictionary lookup for common OCR confusion pairs (e.g., 己↔已↔巳, 土↔士, etc.); loaded from `data/confusion_table.json` and `data/ocr_dictionary.json` |
| Stage 2B | MacBERT CSC | Chinese Spell Correction via `pycorrector` with MacBERT; handles context-sensitive errors Stage 2A misses |
| Stage 2C | LLM Correction | Send text to a local Ollama LLM or OpenRouter API for fluency correction and semantic repair |
| Stage 3A | MinHash Dedup | Fast near-duplicate detection using `datasketch` MinHash LSH; removes repeated paragraphs/pages |
| Stage 3B | BGE-M3 Embedding Dedup | Semantic dedup using `sentence-transformers` with `BAAI/bge-m3`; catches paraphrases that MinHash misses |
| Stage 3C | LLM Semantic Dedup | LLM-assisted deduplication for subtle content repetition (only in API_FULL mode) |

### Pipeline Mode Definitions

---

#### Mode 1: LOCAL_FAST

```
PaddleOCR (GPU) → Stage 1 Cleanup → Stage 2A Rule Corrections → [Stage 3A MinHash] → Output
```

- No LLM, no heavy NLP models
- Fastest mode; add Stage 3A always, Stage 3B only if `dedup_embedding_enabled`
- Best for: high-quality source scans with minimal OCR noise

---

#### Mode 2: LOCAL_STANDARD

```
PaddleOCR (GPU) → Stage 1 → Stage 2A → Stage 2B MacBERT → [Stage 3A] [Stage 3B] → Output
```

- Adds MacBERT spell correction (PyTorch, ~1.5 GB VRAM when loaded)
- **VRAM discipline required:** unload PaddleOCR before loading MacBERT; reload PaddleOCR after
- Good balance of quality and local-only operation

---

#### Mode 3: LOCAL_LLM

```
PaddleOCR (GPU) → Stage 1 → Stage 2A → Stage 2C (Ollama: qwen2.5:7b or qwen3:8b) → [Stage 3A] [Stage 3B] → Output
```

- Requires Ollama running at `ollama_base_url` (default: `http://localhost:11434`)
- Ollama manages its own VRAM separately; qwen2.5:7b-q4_K_M uses ~4.5 GB VRAM
- **VRAM discipline:** PaddleOCR (~1.5 GB) + Ollama model (~4.5 GB) = ~6 GB — within 8 GB budget but tight. Do not load MacBERT or BGE-M3 simultaneously.
- LLM correction prompt (see `correction_llm.py`): ask the model to fix OCR errors in Chinese text without altering meaning, adding or removing content.

---

#### Mode 4: HYBRID_TIERED (Recommended Default)

```
PaddleOCR (GPU) → Stage 1 → Stage 2A
    → confidence > 0.85 (high): done
    → confidence 0.50–0.85 (medium): → Stage 2B MacBERT → done
    → confidence < 0.50 (low): → Stage 2C LLM correction → done
[Stage 3A always] [Stage 3B if enabled]
```

- PaddleOCR returns per-character and per-box confidence scores; use the **minimum box-level confidence** as the routing signal
- Aggregating: for a page/image with multiple text boxes, route each box independently, then reassemble
- Sub-setting `local_llm_model`: choose between Ollama (local) or OpenRouter API for the low-confidence LLM step
- VRAM: same constraints as LOCAL_STANDARD; unload/reload as needed between PaddleOCR and MacBERT stages

---

#### Mode 5: API_STANDARD

```
PaddleOCR (GPU, local always) → Stage 1 → Stage 2A → Stage 2C (OpenRouter API) → [Stage 3A] [Stage 3B] → Output
```

- PaddleOCR always runs locally on GPU; never send raw images to external APIs
- Stage 2C sends cleaned/ruled text to OpenRouter for final correction
- Default model: `deepseek/deepseek-v3.2` (configurable as `openrouter_model_correction`)
- Requires `openrouter_api_key` in config

---

#### Mode 6: API_FULL

```
PaddleOCR (GPU) → Stage 1 → Stage 2A → Stage 2C (OpenRouter) → Stage 3A (MinHash) → Stage 3C (OpenRouter LLM dedup) → Output
```

- Full online post-processing; highest quality, requires API key and network
- Stage 3C sends assembled chapter text to LLM with prompt to identify and remove duplicate/repeated passages
- Default dedup model: `deepseek/deepseek-v3.2` (configurable as `openrouter_model_dedup`)

---

### Deduplication Notes (All Modes)

Stage 3A (MinHash) always runs after correction:

```python
from datasketch import MinHash, MinHashLSH

def build_minhash(text: str, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    for char in text:  # character-level shingles for Chinese
        m.update(char.encode('utf-8'))
    return m

lsh = MinHashLSH(threshold=0.85, num_perm=128)
```

Stage 3B (BGE-M3 embeddings) is opt-in via `dedup_embedding_enabled`:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('BAAI/bge-m3')
embeddings = model.encode(texts, normalize_embeddings=True)
# Cosine similarity > 0.92 → consider duplicate
```

VRAM note: BGE-M3 requires ~2.5 GB VRAM. Do not load simultaneously with PaddleOCR or MacBERT.

---

## 4. Batch / Single OCR Mode (No Capture)

### Batch Mode

- Entry point: "Batch OCR" from the main menu or main window tab
- User selects an input folder via `QFileDialog.getExistingDirectory()`
- The app inspects the folder:
  - If it contains subfolders with images: each subfolder → one chapter. Sort subfolders numerically if all names are integers; otherwise sort alphabetically with a user warning.
  - If it contains images directly (flat structure): treat entire folder as one chapter.
- Supported image formats: PNG, JPG/JPEG, BMP, TIFF, WEBP
- Progress display:
  - Per-folder progress bar (images processed / total images in folder)
  - Overall progress bar (folders processed / total folders)
  - Status label: "Processing folder 3 of 12: image 0045.png"
- Cancel button: sets a `threading.Event` stop flag; the pipeline checks it after each image and exits gracefully after completing the current image (never mid-image).
- Output: same pipeline modes and EPUB output as Capture Mode

### Single OCR Mode

- User selects one or more image files via `QFileDialog.getOpenFileNames()`
- All images treated as one chapter
- Immediate pipeline run; results shown in a text preview widget
- Option to save as plain `.txt` or trigger EPUB export

---

## 5. EPUB Output — Specification

### Library

Use **ebooklib** (`pip install ebooklib`).

### Assembly Logic

```python
from ebooklib import epub
import re

def build_epub(
    session_root: Path,
    folder_ocr_results: dict[int, list[str]],  # folder_num → [text_per_image]
    output_path: Path,
    working_folder_name: str,
) -> Path:
    book = epub.EpubBook()
    book.set_identifier(f"ocr-{working_folder_name}-{timestamp()}")
    book.set_title(f"OCR Export — {working_folder_name}")
    book.set_language('zh-CN')

    css_content = """
    body {
        font-family: "Noto Serif CJK SC", "Source Han Serif CN", serif;
        line-height: 1.8;
        text-indent: 2em;
    }
    p { margin: 0.5em 0; text-indent: 2em; }
    """
    css = epub.EpubItem(
        uid="style_default",
        file_name="style/default.css",
        media_type="text/css",
        content=css_content,
    )
    book.add_item(css)

    chapters = []
    # CRITICAL: numeric sort — never alphabetic
    for folder_num in sorted(folder_ocr_results.keys(), key=lambda x: int(x)):
        texts = folder_ocr_results[folder_num]  # already in image numeric order
        html_parts = []
        for text in texts:
            lines = text.strip().split('\n')
            inner = '<br/>'.join(lines)
            html_parts.append(f'<p>{inner}</p>')
        body_html = '\n'.join(html_parts)

        chapter = epub.EpubHtml(
            title=f'第{folder_num}章',
            file_name=f'chapter_{folder_num:04d}.xhtml',
            lang='zh-CN',
        )
        chapter.content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN" xml:lang="zh-CN">
<head><title>第{folder_num}章</title>
<link rel="stylesheet" type="text/css" href="../style/default.css"/>
</head>
<body>{body_html}</body>
</html>'''
        chapter.add_item(css)
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = tuple(epub.Link(c.file_name, c.title, c.id) for c in chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + chapters

    epub.write_epub(str(output_path), book)
    return output_path
```

### Output Naming

```python
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"{working_folder_name}_{timestamp}.epub"
output_path = Path(config.epub_output_dir) / filename
```

### Typography Notes

- `text-indent: 2em` on all `<p>` elements follows standard Chinese typographic convention for paragraph indentation.
- `line-height: 1.8` provides generous leading for dense CJK character sets.
- Font stack prioritizes open-licensed CJK fonts (`Noto Serif CJK SC`, `Source Han Serif CN`) with generic serif fallback. Users should install these fonts for best results; EPUB readers on Windows/Android typically have adequate CJK font support built in.

---

## 6. GitHub Integration

### Library

Use **gitpython** (`pip install gitpython`). Do not use `subprocess` calls to the `git` CLI — gitpython provides a clean Python API that is easier to test and mock.

### First-Run Setup

On first launch (or when `github_repo_path` is not set in config), show a dialog with options:
1. **Initialize new repo**: specify a local path → `git init` → optionally add remote URL → initial commit
2. **Clone existing repo**: specify remote URL + local target path → `git clone`
3. **Skip**: no GitHub integration for this session

```python
from git import Repo, InvalidGitRepositoryError

class RepoManager:
    def __init__(self, repo_path: Path):
        try:
            self.repo = Repo(repo_path)
        except InvalidGitRepositoryError:
            self.repo = Repo.init(repo_path)

    def auto_commit(self, folder_name: str) -> str:
        self.repo.git.add(A=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"OCR batch: {folder_name} {timestamp}"
        commit = self.repo.index.commit(message)
        return commit.hexsha

    def push(self, remote_name: str = "origin", branch: str = "main"):
        remote = self.repo.remote(remote_name)
        remote.push(branch)
```

### Workflow

1. After each completed OCR batch (all folders in a session processed), if `github_auto_commit` is true: stage all files, commit with the message format `"OCR batch: {folder_name} {timestamp}"`.
2. If `github_auto_push` is true: push to `github_remote_url` after commit.
3. Errors in git operations (network down, auth failure, etc.) must NOT crash the app or lose OCR results. Catch all git exceptions, log them, and show a non-blocking notification in the status bar.

### Branch Strategy (for Claude Code development)

- `main`: stable, passing-tests builds only
- `dev`: active development integration branch
- Feature branches: `feature/capture-overlay`, `feature/ocr-pipeline`, `feature/epub-output`, etc.
- Merge to `dev` first; merge `dev` to `main` only when a phase milestone is complete and all tests pass.

---

## 7. Configuration File (`config.json`)

All configuration lives in a single `config.json` at the project root. An `config.example.json` (with placeholder API keys) is committed to git; the actual `config.json` is gitignored.

### Schema

```jsonc
{
  // Base directory under which all session folders are created
  "working_root_dir": "D:/ocr_sessions",

  // Current capture region in screen coordinates
  "capture_region": {
    "x": 0,
    "y": 0,
    "width": 800,
    "height": 600
  },

  // Rotation applied to captured images
  // Values: "none" | "90cw" | "90ccw" | "180" | "auto"
  "rotation_mode": "none",

  // System-wide hotkey bindings (pynput key name strings)
  "keybindings": {
    "capture": "f9",
    "new_section": "f10",
    "send_to_ocr": "f11",
    "reset_area": "f8",
    "toggle_overlay": "f7"
  },

  // OCR pipeline mode
  // Values: "LOCAL_FAST" | "LOCAL_STANDARD" | "LOCAL_LLM" | "HYBRID_TIERED" | "API_STANDARD" | "API_FULL"
  "ocr_pipeline_mode": "HYBRID_TIERED",

  // OpenRouter configuration (required for API_STANDARD, API_FULL)
  "openrouter_api_key": "",
  "openrouter_model_correction": "deepseek/deepseek-v3.2",
  "openrouter_model_dedup": "deepseek/deepseek-v3.2",

  // Local LLM via Ollama (required for LOCAL_LLM and HYBRID_TIERED with local sub-setting)
  "local_llm_model": "qwen2.5:7b-instruct-q4_K_M",
  "ollama_base_url": "http://localhost:11434",

  // Deduplication stage settings
  "dedup_embedding_enabled": false,
  "dedup_llm_enabled": false,

  // HYBRID_TIERED confidence routing thresholds
  "confidence_thresholds": {
    "high": 0.85,
    "low": 0.50
  },

  // EPUB output directory
  "epub_output_dir": "D:/ocr_sessions/epub_output",

  // GitHub integration
  "github_repo_path": "",
  "github_remote_url": "",
  "github_auto_commit": true,
  "github_auto_push": false,

  // PaddleOCR settings
  "paddleocr_use_gpu": true,
  "paddleocr_lang": "ch"
}
```

### ConfigManager

```python
# utils/config_manager.py
import json
from pathlib import Path
from dataclasses import dataclass, field

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

class ConfigManager:
    def __init__(self, path: Path = CONFIG_PATH):
        self._path = path
        self._data: dict = {}
        self.load()

    def load(self):
        if self._path.exists():
            with open(self._path, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def save(self):
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        keys = key.split('.')
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, default)
            else:
                return default
        return val

    def set(self, key: str, value):
        keys = key.split('.')
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        self.save()
```

---

## 8. Project File/Folder Structure

```
chinese_ocr_app/
├── main.py                        # Entry point — QApplication init, main window show, hotkey listener start
├── config.json                    # User config (gitignored — contains API keys)
├── config.example.json            # Example config with placeholder values (committed)
├── requirements.txt               # pip-installable dependencies
├── environment.yml                # Conda environment spec (Python 3.11, base packages)
├── pyproject.toml                 # Project metadata (name, version, build system)
├── .gitignore                     # Excludes: config.json, __pycache__, *.pyc, .paddle/, *.epub (optional)
├── README.md                      # Setup instructions, usage, keybinding reference
│
├── gui/
│   ├── __init__.py
│   ├── main_window.py             # QMainWindow: tabs/toolbar for Capture, Batch, Single modes
│   ├── capture_overlay.py         # CaptureOverlay QWidget — full-screen rubber-band selector
│   ├── region_border.py           # RegionBorderOverlay — always-on-top non-interactive border
│   ├── settings_dialog.py         # QDialog for all config.json settings
│   └── batch_dialog.py            # QDialog for Batch OCR folder selection and progress
│
├── capture/
│   ├── __init__.py
│   ├── screen_capture.py          # mss-based screenshot capture; returns PIL Image or numpy array
│   ├── rotation.py                # Fixed rotation + auto-detect (aspect ratio + Hough lines)
│   └── session.py                 # SessionManager: folder creation, image counter, numeric sort
│
├── ocr/
│   ├── __init__.py
│   ├── engine.py                  # OCREngine: PaddleOCR init, model lifecycle, unload/reload
│   ├── pipeline.py                # PipelineOrchestrator: dispatches to correct mode based on config
│   ├── cleanup.py                 # Stage 1: raw text cleanup functions
│   ├── correction_rules.py        # Stage 2A: confusion table and dictionary corrections
│   ├── correction_bert.py         # Stage 2B: MacBERT/pycorrector CSC
│   ├── correction_llm.py          # Stage 2C: Ollama local LLM or OpenRouter API correction
│   └── dedup.py                   # Stage 3A MinHash, Stage 3B BGE-M3, Stage 3C LLM dedup
│
├── epub/
│   ├── __init__.py
│   └── builder.py                 # EPUBBuilder: assembles chapters in numeric order via ebooklib
│
├── github_integration/
│   ├── __init__.py
│   └── repo_manager.py            # RepoManager: gitpython-based init, commit, push, error handling
│
├── utils/
│   ├── __init__.py
│   ├── config_manager.py          # ConfigManager: load/save/get/set config.json
│   ├── file_utils.py              # Numeric sort helpers, path validation, image discovery
│   └── logging_config.py          # Structured logging: rotating file handler + console handler
│
├── data/
│   ├── confusion_table.json       # Chinese OCR character confusion pairs {wrong: correct, ...}
│   └── ocr_dictionary.json        # Domain-specific vocabulary for rule correction
│
└── tests/
    ├── __init__.py
    ├── test_file_utils.py          # CRITICAL: numeric sort correctness tests
    ├── test_epub_builder.py        # Chapter order, content assembly, lang attribute
    ├── test_cleanup.py             # Stage 1 cleanup unit tests
    ├── test_correction_rules.py    # Stage 2A rule correction tests
    ├── test_config_manager.py      # Load/save/get/set config round-trips
    └── test_pipeline_mock.py       # Full pipeline integration tests with mocked PaddleOCR
```

---

## 9. Dependency and Conflict Notes

### Critical Install Order

This is the correct installation sequence for a fresh Windows environment. Deviating from this order is a known source of conflicts.

#### Step 1: Create Conda Environment

```bash
conda create -n ocr_env python=3.11 -y
conda activate ocr_env
```

Use Python **3.11**. PaddlePaddle 3.x has known issues with Python 3.12+. Python 3.10 is also acceptable but 3.11 is preferred for its performance improvements.

#### Step 2: Install NumPy, Pillow, OpenCV via Conda

```bash
conda install -c conda-forge numpy pillow -y
conda install -c conda-forge opencv -y
```

Installing OpenCV via conda-forge avoids the Qt/OpenCV GUI conflict on Windows (where `opencv-python` from PyPI bundles a Qt runtime that conflicts with PySide6). After conda install, also install the headless pip version to ensure the correct one is used:

```bash
pip install opencv-python-headless
```

#### Step 3: Install PySide6

```bash
pip install PySide6
```

Install before PaddlePaddle. PySide6 has no conflicts with PaddlePaddle at the package level.

#### Step 4: Install PaddlePaddle GPU — Non-Standard Index

```bash
pip install paddlepaddle-gpu==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
```

**Critical notes:**
- Use **only** the official PaddlePaddle index. PyPI's `paddlepaddle-gpu` package is outdated.
- Supports CUDA up to **12.9**. Does **not** support CUDA 13.x+. Verify your driver supports CUDA 12.x: run `nvidia-smi` and check the CUDA version in the top-right corner.
- If CUDA version shown in `nvidia-smi` is 12.x, use `cu126` in the index URL. If your CUDA toolkit is a different 12.x sub-version, `cu126` still works because PaddlePaddle is forward-compatible within 12.x.
- **Do NOT use `uv`** to install paddlepaddle-gpu. `uv` has a known issue with the non-standard wheel naming (`paddlepaddle-gpu` vs `paddlepaddle_gpu`) that causes it to fail or install the wrong (CPU) variant. Use plain `pip`.

#### Step 5: Install PaddleOCR

```bash
pip install paddleocr
```

#### Step 6: Install PyTorch (for MacBERT, BGE-M3, sentence-transformers)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

PyTorch and PaddlePaddle can coexist in the same environment. Both use CUDA but manage their own contexts independently. They will not conflict at the Python/package level. Monitor total VRAM at runtime (see VRAM budget below).

#### Step 7: Install Remaining Dependencies

```bash
pip install pyside6 mss ebooklib pycorrector datasketch sentence-transformers gitpython openai pynput
```

`openai` is used for OpenRouter API calls (OpenRouter exposes an OpenAI-compatible API endpoint).

### VRAM Budget (RTX 4070, 8 GB)

This is the most important operational constraint. Never exceed ~7.5 GB total to leave headroom for the OS and display.

| Component | Approx. VRAM | Notes |
|---|---|---|
| PaddleOCR (PP-OCRv4, GPU) | ~1.2–1.8 GB | Loaded for all modes |
| MacBERT CSC (pycorrector) | ~1.2–1.6 GB | PyTorch; load/unload around OCR |
| Ollama qwen2.5:7b-q4_K_M | ~4.3–4.8 GB | Managed by Ollama process separately |
| BGE-M3 (sentence-transformers) | ~2.2–2.8 GB | PyTorch; load/unload around OCR |
| Windows desktop + display | ~0.3–0.5 GB | Always present |

**Simultaneous load rules:**
- PaddleOCR alone: safe
- PaddleOCR + MacBERT: safe (~3–3.4 GB total ML), but unload before adding more
- PaddleOCR + Ollama: Ollama is a separate process; combined approaches ~6–6.5 GB — within budget, no MacBERT/BGE-M3
- PaddleOCR + BGE-M3: ~4 GB — safe for dedup phase only (unload PaddleOCR first for headroom)
- PaddleOCR + MacBERT + BGE-M3: **DO NOT DO THIS** — will OOM or swap to system RAM with severe performance degradation

**Implement explicit model management in `engine.py`:**

```python
class ModelContext:
    """Context manager for loading/unloading models around OCR stages."""

    def __init__(self, load_fn, unload_fn):
        self._load = load_fn
        self._unload = unload_fn

    def __enter__(self):
        self._load()
        return self

    def __exit__(self, *args):
        self._unload()
```

### Other Known Conflicts and Issues

**pynput vs keyboard library:**  
Use `pynput` for global hotkeys. The `keyboard` library requires Administrator/elevated privileges in some Windows configurations (especially on systems with Secure Boot or enterprise security policies). `pynput` operates in user space without elevation requirements.

**pycorrector dependencies:**  
`pycorrector` installs `torch`, `transformers`, `datasets`, and related packages. Pin versions in `requirements.txt` to prevent incompatible upgrades. Tested combination: `pycorrector>=0.6.0`, `torch>=2.1.0`, `transformers>=4.35.0`.

**sentence-transformers + torch:**  
`sentence-transformers` will pull PyTorch if not already installed. Since PyTorch is installed in Step 6, this should be a no-op. Verify with `pip show sentence-transformers torch` that versions are compatible.

**ebooklib maintenance status:**  
`ebooklib` is minimally maintained. Use version `>=0.18`. Known limitation: does not validate EPUB3 output against the full spec. Use `epubcheck` (separate Java tool) to validate final EPUBs if spec compliance matters for your distribution target.

**OpenRouter API client:**  
Use the `openai` Python library pointed at the OpenRouter base URL:

```python
from openai import OpenAI

client = OpenAI(
    api_key=config.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
)

response = client.chat.completions.create(
    model=config.openrouter_model_correction,
    messages=[
        {"role": "system", "content": "你是一个专业的中文OCR校对助手。"},
        {"role": "user", "content": f"请校正以下OCR识别文本中的错误，保持原意不变：\n\n{text}"}
    ],
    temperature=0.1,
)
corrected = response.choices[0].message.content
```

---

## 10. Windsurf Development Workflow & Project Structure

### 10.0 Why Windsurf (vs Claude Code)

Windsurf's Cascade agent is used instead of Claude Code for this project. Cascade provides an IDE-native experience: visual diff review before accepting each file change, inline editing with full multi-file transparency, and step-by-step editing visibility in the chat panel. It stays in the VS Code-compatible IDE paradigm, which keeps the developer in one environment for writing, running, and committing code.

The `.windsurfrules` file gives Cascade persistent project context (architecture rules, anti-patterns, naming conventions) without consuming chat context per-message. This means Cascade "knows the rules" from the start of every session without you having to re-explain them.

---

### 10.1 Windsurf Key Concepts for This Project

- **Cascade**: Windsurf's AI agent. Can read/write files, run terminal commands, and perform multi-file edits. Use it for all feature implementation.
- **Rules**: Persistent instructions to Cascade. Project rules live in `.windsurfrules` at project root. 6,000 character limit. Always active. Do not put verbose content here — put pointers to docs files instead.
- **Memories**: Windsurf's built-in persistent memory. Cascade can create and recall memories across sessions. Use for: decisions made, patterns established, bugs fixed. NOT a substitute for docs files.
- **@file references**: In Cascade chat, use `@filename` to pull a specific file into Cascade's context. Use this to pull in guideline docs when working on relevant areas: `@ocr_guidelines.md`, `@app_guidelines.md`.
- **Glob rules**: Windsurf supports file-pattern-triggered rules (e.g., trigger a rule when editing `*.py`). The `.windsurfrules` uses this for stage-specific guidance.

---

### 10.2 Recommended Project docs/ Structure (Windsurf Workflow Files)

These files live in the project root alongside `.windsurfrules` and are the living project state that Cascade reads:

```
chinese_ocr_app/
├── .windsurfrules              # Cascade project rules (≤6000 chars) — DO NOT bloat
├── docs/
│   ├── ocr_guidelines.md       # OCR pipeline reference (this repo's ocr_guidelines.md)
│   ├── app_guidelines.md       # App architecture reference (this file)
│   ├── NEXT_STEPS.md           # What to work on next; updated after each session
│   ├── CHANGELOG.md            # Keep-a-Changelog format; updated after each feature
│   ├── DECISIONS.md            # Architecture decisions and their rationale
│   └── KNOWN_ISSUES.md         # Active bugs and workarounds
├── ... (rest of project)
```

**NEXT_STEPS.md** — Critical for Windsurf session continuity. At the end of each Cascade session, ask Cascade: "Update NEXT_STEPS.md with what was completed and what comes next." At the start of a new session, reference it: `@NEXT_STEPS.md` in the first message.

**CHANGELOG.md** — Use Keep a Changelog format. Cascade should append an entry after each completed feature. Gives a history GitHub PRs can reference.

**DECISIONS.md** — When an architectural decision is made (e.g., "chose `__init_subclass__` registry over entry_points because..."), record it here. Prevents Cascade from relitigating settled decisions in future sessions.

**KNOWN_ISSUES.md** — Track active bugs with reproduction steps. Cascade references this to avoid introducing known-broken patterns.

---

### 10.3 GitHub Workflow with Windsurf

Windsurf has built-in Git integration via the Source Control panel. The workflow:

1. **Branch strategy**: `main` → stable releases; `dev` → active development; `feature/FEAT-name` → individual features from ARCH/FEAT ticket IDs.
2. **Commit discipline**: Commit after each completed ticket (not mid-ticket). Message format: `[TICKET-ID] Brief description`. Example: `[ARCH-001] Implement Registrable registry pattern`.
3. **PR workflow**: Feature branches → PR → merge to `dev`. Periodically merge `dev` → `main` for stable snapshots.
4. **GitHub as distribution**: For sharing with Discord friends, GitHub releases work well. Tag stable versions (`v0.1.0-alpha`). Friends can clone and run with the `environment.yml`.
5. **gitpython vs Windsurf Git panel**: Use Windsurf's Source Control panel for commits/pushes during development. The in-app `gitpython` (in `github_integration/`) handles automated post-export commits, not developer workflow.
6. **`.gitignore` essentials** for this project: `config.json` (has API keys), `__pycache__/`, `*.pyc`, `.paddle/`, `~/.paddleocr/` model cache should NOT be committed (large binaries), `*.epub` output files, conda env directory if local.

---

### 10.4 Cascade Session Pattern (Recommended Workflow)

Each development session should follow this pattern:

```
Session Start:
1. Open Windsurf, activate conda env in terminal: conda activate chinese-ocr
2. First Cascade message: "@NEXT_STEPS.md — continue from where we left off.
   We're working on [TICKET-ID]."
3. Reference relevant docs as needed: @app_guidelines.md @ocr_guidelines.md

During Session:
4. Let Cascade plan before coding: "Plan the implementation of [TICKET-ID],
   then wait for my approval before writing any code."
5. Review Cascade's step-by-step edits in the diff view before accepting.
6. Run tests after each file change: Cascade can run `pytest tests/` in terminal.
7. Commit completed tickets via Source Control panel.

Session End:
8. Ask Cascade: "Update NEXT_STEPS.md: mark [TICKET-ID] complete,
   list what's next, note any decisions made."
9. Ask Cascade: "Append to CHANGELOG.md for [TICKET-ID]."
10. Push to GitHub: `git push origin feature/FEAT-name`
```

---

### 10.5 Cascade Context Management

Cascade has a context window limit. For this project (large codebase + long guideline docs):

- **Do not paste entire guideline docs into chat** — use `@file` references instead. Cascade reads the file selectively.
- **Keep one topic per session** — don't try to implement OCR engine AND EPUB output in one session. Work ticket by ticket.
- **If Cascade loses context**: Remind it with `@NEXT_STEPS.md @DECISIONS.md` and the current ticket ID.
- **Memories over re-explanation**: When Cascade establishes a pattern that worked (e.g., "always unload PaddleOCR before loading MacBERT"), ask it to save to Windsurf memory so it doesn't need re-explanation next session.

---

### 10.6 Testing Strategy

#### Framework

Use **pytest**. Install: `pip install pytest pytest-cov pytest-mock`.

#### Critical Tests (Must Pass Before Any Merge to `main`)

#### Numeric Sort Tests — P0

```python
# tests/test_file_utils.py

def test_folder_sort_numeric_not_lexicographic():
    """Verifies that folder sort never produces 1, 10, 2 order."""
    from utils.file_utils import sort_folders_numeric
    folders = ["10", "2", "1", "20", "11", "3"]
    result = sort_folders_numeric(folders)
    assert result == ["1", "2", "3", "10", "11", "20"], (
        f"Got {result} — lexicographic sort detected, this is a fatal bug"
    )

def test_image_sort_numeric():
    """Verifies image filename sort is numeric."""
    from utils.file_utils import sort_images_numeric
    images = ["0010.png", "0002.png", "0001.png", "0100.png"]
    result = sort_images_numeric(images)
    assert result == ["0001.png", "0002.png", "0010.png", "0100.png"]

def test_folder_sort_single_digit():
    folders = ["3", "1", "2"]
    from utils.file_utils import sort_folders_numeric
    assert sort_folders_numeric(folders) == ["1", "2", "3"]
```

#### EPUB Chapter Order Tests

```python
# tests/test_epub_builder.py

def test_epub_chapters_in_numeric_order(tmp_path):
    """Verifies EPUB spine and TOC are in 1, 2, 3 order, not 1, 10, 2."""
    from epub.builder import build_epub
    results = {
        10: ["第十章文字"],
        2: ["第二章文字"],
        1: ["第一章文字"],
    }
    output = build_epub(tmp_path, results, tmp_path / "test.epub", "001")
    # Parse the resulting EPUB and verify spine order
    import zipfile
    with zipfile.ZipFile(output) as z:
        content_opf = z.read("EPUB/content.opf").decode()
    # Chapter 1 should appear before Chapter 2, Chapter 2 before Chapter 10
    pos1 = content_opf.find("chapter_0001")
    pos2 = content_opf.find("chapter_0002")
    pos10 = content_opf.find("chapter_0010")
    assert pos1 < pos2 < pos10, "EPUB chapter order is wrong"
```

#### Pipeline Mock Tests

```python
# tests/test_pipeline_mock.py

from unittest.mock import patch, MagicMock

def test_local_fast_pipeline_runs(tmp_path):
    mock_paddle_result = [
        [["识别文字", 0.98], [[10, 10], [100, 10], [100, 30], [10, 30]]]
    ]
    with patch("ocr.engine.PaddleOCR") as MockPaddle:
        MockPaddle.return_value.ocr.return_value = [mock_paddle_result]
        from ocr.pipeline import PipelineOrchestrator
        orch = PipelineOrchestrator(mode="LOCAL_FAST")
        result = orch.process_image(tmp_path / "fake.png")
        assert "识别文字" in result

def test_hybrid_tiered_routes_low_confidence_to_llm():
    """Low confidence text should be routed to LLM correction stage."""
    # ... mock PaddleOCR returning confidence 0.3, assert correction_llm is called
```

#### Config Manager Round-Trip Tests

```python
# tests/test_config_manager.py

def test_config_save_load_roundtrip(tmp_path):
    from utils.config_manager import ConfigManager
    cfg = ConfigManager(tmp_path / "config.json")
    cfg.set("capture_region.x", 42)
    cfg.set("ocr_pipeline_mode", "LOCAL_FAST")
    cfg2 = ConfigManager(tmp_path / "config.json")
    assert cfg2.get("capture_region.x") == 42
    assert cfg2.get("ocr_pipeline_mode") == "LOCAL_FAST"
```

#### Test Coverage Targets

- `utils/file_utils.py`: 100% (sorting is critical correctness)
- `epub/builder.py`: 90%+ (chapter order, content assembly)
- `ocr/cleanup.py`: 80%+
- `ocr/correction_rules.py`: 80%+
- `utils/config_manager.py`: 90%+

Run coverage: `pytest --cov=. --cov-report=html tests/`

#### CI Notes

- PaddleOCR requires GPU in production but must be mockable in CI
- All tests that touch `ocr/engine.py` must mock `PaddleOCR` to avoid GPU dependency
- GitHub Actions runner: use `ubuntu-latest` or `windows-latest` without GPU; all GPU-dependent code must be behind the mock layer

---

---

## 11. Plugin & Extensibility Architecture

This section defines the extensibility contract for the entire codebase. Every major subsystem implementation must follow these patterns. This is not optional — it is the architectural backbone that allows future modules to be added without modifying existing code.

### 11.1 Core Design Principle: Open/Closed

The app must be **Open for Extension, Closed for Modification**. Every major subsystem (OCR engines, post-processing stages, output formats, input sources, LLM providers, language modules) must be designed so that:

- New implementations are added by creating new files/classes, never by editing existing ones
- The core pipeline orchestrator discovers and routes to implementations via a registry, not `if/elif` chains
- No existing unit test should break when a new feature module is added

### 11.2 The Registry Pattern (Primary Mechanism)

Use Python's `__init_subclass__` hook + ABC for self-registering components. This is the cleanest approach for this codebase — no external framework needed, works at import time, requires zero configuration files.

```python
# core/registry.py
from abc import ABC, abstractmethod
from typing import ClassVar, Dict, Type, TypeVar

T = TypeVar('T', bound='Registrable')

class Registrable(ABC):
    """Base class for all auto-registering plugin components."""
    _registry: ClassVar[Dict[str, Type]] = {}
    registry_name: ClassVar[str]  # Subclasses must define this

    def __init_subclass__(cls, name: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if name is not None:  # Abstract intermediates don't register
            cls.registry_name = name
            cls._registry[name] = cls

    @classmethod
    def get(cls: Type[T], name: str) -> Type[T]:
        if name not in cls._registry:
            raise KeyError(f"No {cls.__name__} registered as '{name}'. "
                           f"Available: {list(cls._registry.keys())}")
        return cls._registry[name]

    @classmethod
    def list_registered(cls) -> list[str]:
        return list(cls._registry.keys())
```

This pattern means: to add a new OCR engine, you create a new file that subclasses `OCREngine` with `name="my_engine"`. Import it anywhere before use and it auto-registers. The orchestrator calls `OCREngine.get("my_engine")()` — no changes to existing code.

### 11.3 Core Registrable Interfaces

Define these ABC interfaces, each inheriting from `Registrable`:

#### OCREngine (`ocr/engines/base.py`)

```python
class OCREngine(Registrable):
    @abstractmethod
    def initialize(self, config: dict) -> None: ...
    @abstractmethod
    def recognize(self, image: np.ndarray) -> list[OCRResult]: ...
    @abstractmethod
    def unload(self) -> None: ...
    @property
    @abstractmethod
    def vram_mb(self) -> int: ...  # Approximate VRAM footprint
```

Implementations: `PaddleOCREngine(name="paddleocr")`, `RapidOCREngine(name="rapidocr")`

#### PostProcessStage (`ocr/stages/base.py`)

```python
class PostProcessStage(Registrable):
    @abstractmethod
    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]: ...
    @property
    @abstractmethod
    def stage_id(self) -> str: ...
```

Implementations: `CleanupStage(name="cleanup")`, `RuleCorrectionStage(name="rule_correction")`, `BERTCorrectionStage(name="bert_correction")`, `LLMCorrectionStage(name="llm_correction")`, `MinHashDedupStage(name="minHash_dedup")`, `EmbeddingDedupStage(name="embedding_dedup")`

#### OutputFormatter (`output/base.py`)

```python
class OutputFormatter(Registrable):
    @abstractmethod
    def format(self, chapters: list[Chapter], config: dict) -> bytes: ...
    @abstractmethod
    def file_extension(self) -> str: ...
```

Implementations: `EpubFormatter(name="epub")`, future: `TxtFormatter(name="txt")`, `MarkdownFormatter(name="markdown")`, `DocxFormatter(name="docx")`

#### InputSource (`input/base.py`)

```python
class InputSource(Registrable):
    @abstractmethod
    def acquire(self, config: dict) -> Iterator[tuple[str, np.ndarray]]: ...
    # Yields (image_id, image_array) tuples
```

Implementations: `ScreenCaptureSource(name="screen_capture")`, `FilesystemSource(name="filesystem")`, future: `WebScraperSource(name="web_scraper")`, `ZipSource(name="zip")`

#### LLMProvider (`llm/base.py`)

```python
class LLMProvider(Registrable):
    @abstractmethod
    def complete(self, messages: list[dict], config: dict) -> str: ...
    @abstractmethod
    def is_available(self) -> bool: ...
```

Implementations: `OpenRouterProvider(name="openrouter")`, `OllamaProvider(name="ollama")`

#### TranslationPipeline (`translation/base.py`) — stub for future use

```python
class TranslationPipeline(Registrable):
    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str, context: dict) -> str: ...
```

### 11.4 Pipeline Orchestrator

`ocr/pipeline.py` becomes a pure orchestrator — it reads a pipeline mode definition from config and assembles stages dynamically:

```python
# Pipeline modes defined in config as ordered stage lists, not hardcoded
PIPELINE_MODES = {
    "LOCAL_FAST":      ["cleanup", "rule_correction"],
    "LOCAL_STANDARD":  ["cleanup", "rule_correction", "bert_correction"],
    "LOCAL_LLM":       ["cleanup", "rule_correction", "llm_correction"],
    "HYBRID_TIERED":   ["cleanup", "rule_correction", "tiered_correction"],
    "API_STANDARD":    ["cleanup", "rule_correction", "llm_correction"],
    "API_FULL":        ["cleanup", "rule_correction", "llm_correction", "embedding_dedup"],
}

class PipelineOrchestrator:
    def run(self, images, mode: str, config: dict) -> list[OCRResult]:
        ocr_engine = OCREngine.get(config["ocr_engine"])()
        ocr_engine.initialize(config)
        raw = ocr_engine.recognize(images)
        ocr_engine.unload()

        stages = [PostProcessStage.get(s)() for s in PIPELINE_MODES[mode]]
        for stage in stages:
            raw = stage.process(raw, config)
        return raw
```

Adding a new pipeline mode = add an entry to `PIPELINE_MODES`. Adding a new stage = add a new file. No other changes.

### 11.5 VRAM Manager

Central VRAM budget tracker that all model-loading components must consult:

```python
# core/vram_manager.py
class VRAMManager:
    def __init__(self, total_mb: int):
        self.total_mb = total_mb
        self._allocated: dict[str, int] = {}

    def can_allocate(self, name: str, mb: int) -> bool:
        return (sum(self._allocated.values()) + mb) <= self.total_mb

    def allocate(self, name: str, mb: int) -> bool:
        if not self.can_allocate(name, mb):
            return False
        self._allocated[name] = mb
        return True

    def release(self, name: str):
        self._allocated.pop(name, None)

    @property
    def available_mb(self) -> int:
        return self.total_mb - sum(self._allocated.values())
```

Every `OCREngine`, `PostProcessStage`, and `LLMProvider` declares its `vram_mb` and must call `vram_manager.allocate(self.name, self.vram_mb)` before loading and `vram_manager.release(self.name)` after unloading. The orchestrator holds the singleton VRAMManager and passes it to all components.

### 11.6 Module Boundaries for Future Features

Define these as empty-but-structured stubs in the initial project. They exist as directories with `__init__.py` and `base.py` (the ABC) only — no implementation yet. This ensures the architecture slots for them without any code commitment:

```
modules/
├── translation/
│   ├── __init__.py
│   ├── base.py          # TranslationPipeline ABC
│   └── README.md        # "Future: LLM-based translation with per-story memory"
├── manga/
│   ├── __init__.py
│   ├── base.py          # MangaProcessor ABC
│   └── README.md        # "Future: speech bubble detection, panel ordering, CBZ/ZIP input"
├── web_scraper/
│   ├── __init__.py
│   ├── base.py          # WebScraper ABC
│   └── README.md        # "Future: novel/fiction web scraping with chapter detection"
└── story_memory/
    ├── __init__.py
    ├── base.py          # StoryMemory ABC (vector store + per-story context)
    └── README.md        # "Future: per-story LLM memory for translation consistency"
```

**MangaProcessor ABC** (key interface for future comic/manga mode):

```python
class MangaProcessor(Registrable):
    @abstractmethod
    def detect_panels(self, image: np.ndarray) -> list[Panel]: ...
    @abstractmethod
    def detect_bubbles(self, panel: Panel) -> list[TextBubble]: ...
    @abstractmethod
    def order_reading_sequence(self, panels: list[Panel]) -> list[Panel]: ...
    # Reading order for manga is typically right-to-left, top-to-bottom
```

**StoryMemory ABC** (key for translation consistency):

```python
class StoryMemory(Registrable):
    @abstractmethod
    def store_term(self, story_id: str, original: str, translation: str) -> None: ...
    @abstractmethod
    def lookup_term(self, story_id: str, original: str) -> str | None: ...
    @abstractmethod
    def get_context(self, story_id: str, n_recent: int = 5) -> list[str]: ...
```

### 11.7 Event Bus (Loose Coupling Between Modules)

Use a lightweight internal event bus so modules can react to events without direct coupling:

```python
# core/event_bus.py
from collections import defaultdict
from typing import Callable

class EventBus:
    def __init__(self):
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable) -> None:
        self._listeners[event].append(callback)

    def publish(self, event: str, **kwargs) -> None:
        for cb in self._listeners[event]:
            cb(**kwargs)

# Singleton
event_bus = EventBus()
```

Key events to publish (others can subscribe without coupling):

- `ocr.image_complete` (image_id, results, confidence_avg)
- `ocr.batch_complete` (folder_id, result_count)
- `capture.new_image` (image_id, folder_id, image_array)
- `capture.new_section` (folder_id)
- `export.complete` (output_path, chapter_count)
- `pipeline.stage_complete` (stage_name, input_count, output_count)

The GUI subscribes to these events for progress display. The GitHub integration subscribes to `export.complete` for auto-commit. Future modules subscribe to `capture.new_image` for additional processing — all without modifying existing code.

### 11.8 Configuration Schema — Extensibility Keys

Add these to the config.json schema (supplement the existing schema in Section 7):

- `vram_tier`: `"8gb"` | `"16gb"` — selects model recommendations and VRAM budget
- `vram_budget_mb`: integer, default derived from tier (8192 or 16384), overridable
- `ocr_engine`: `"paddleocr"` | `"rapidocr"` — which registered OCREngine to use
- `output_format`: `"epub"` — which registered OutputFormatter to use (extensible)
- `enabled_modules`: list of module names, e.g. `["epub"]` — future: `["epub", "translation"]`
- `pipeline_mode_custom`: optional dict defining a custom stage list (power user feature)

### 11.9 Updated Project Structure

The following directory tree shows the updated layout with module stubs:

```
chinese_ocr_app/
├── core/
│   ├── __init__.py
│   ├── registry.py          # Registrable base + __init_subclass__ registry
│   ├── vram_manager.py      # VRAMManager singleton
│   └── event_bus.py         # EventBus singleton
├── ocr/
│   ├── engines/
│   │   ├── base.py          # OCREngine ABC
│   │   ├── paddle_engine.py # PaddleOCREngine(name="paddleocr")
│   │   └── rapid_engine.py  # RapidOCREngine(name="rapidocr")
│   ├── stages/
│   │   ├── base.py          # PostProcessStage ABC
│   │   ├── cleanup.py       # CleanupStage(name="cleanup")
│   │   ├── rule_correction.py
│   │   ├── bert_correction.py
│   │   ├── llm_correction.py
│   │   ├── minHash_dedup.py
│   │   └── embedding_dedup.py
│   └── pipeline.py          # PipelineOrchestrator — reads registry, no hardcoding
├── output/
│   ├── base.py              # OutputFormatter ABC
│   └── epub_formatter.py    # EpubFormatter(name="epub")
├── input/
│   ├── base.py              # InputSource ABC
│   ├── screen_capture.py    # ScreenCaptureSource(name="screen_capture")
│   └── filesystem.py        # FilesystemSource(name="filesystem")
├── llm/
│   ├── base.py              # LLMProvider ABC
│   ├── openrouter.py        # OpenRouterProvider(name="openrouter")
│   └── ollama.py            # OllamaProvider(name="ollama")
├── modules/                 # Future feature stubs
│   ├── translation/
│   ├── manga/
│   ├── web_scraper/
│   └── story_memory/
├── gui/
│   └── ... (as before)
├── capture/
│   └── ... (as before)
├── epub/                    # Legacy — will be absorbed into output/ but keep for now
├── utils/
│   └── ... (as before)
└── tests/
    ├── test_registry.py     # Verify registration works, no duplicate names
    ├── test_vram_manager.py
    └── ... (as before)
```

---

## 12. VRAM Tier System

### 12.1 Tier Definitions

Two supported tiers. The tier is set in `config.json` as `vram_tier`. The VRAMManager is initialized with the corresponding budget.

| Tier | VRAM | Target hardware | vram_budget_mb default |
|------|------|-----------------|----------------------|
| `8gb` | 8 GB | RTX 4070 Laptop, RTX 3070, RTX 4060 | 7680 (leave 512 MB for system) |
| `16gb` | 16 GB | RTX 4080, RTX 4070 Ti, RTX 3080 16GB | 15360 |

### 12.2 Model Selection by Tier

**OCR Engine — same for both tiers** (PaddleOCR PP-OCRv5 ~2 GB):

| Component | 8 GB Tier | 16 GB Tier |
|-----------|-----------|------------|
| PaddleOCR | PP-OCRv5, ~1.5 GB | PP-OCRv5, ~1.5 GB |
| CSC BERT | MacBERT-base (~2 GB) | MacBERT-large (~4 GB) |
| Embedding | BGE-M3 FP16 (~1.1 GB) | BGE-M3 FP16 (~1.1 GB), can stay resident |
| Local LLM (correction) | Qwen2.5-7B Q4_K_M (~5 GB) | Qwen2.5-14B Q4_K_M (~10 GB) |
| Local LLM (dedup judge) | Qwen2.5-7B Q4_K_M (shared) | Qwen3-14B Q4_K_M or Qwen2.5-14B |
| Inference speed (7B) | ~52 tok/sec (RTX 4070) | ~52 tok/sec |
| Inference speed (14B) | N/A (exceeds VRAM) | ~33 tok/sec (RTX 4070 12GB ref) |

**16 GB tier additional capabilities:**

- MacBERT-large can run concurrently with BGE-M3 (combined ~5 GB, below 16 GB with OCR unloaded)
- BGE-M3 can stay resident between OCR batches (no unload/reload cycle needed)
- Qwen2.5-14B fits with room for KV cache (~10 GB model + ~2-3 GB KV = ~12-13 GB, fits in 16 GB after OCR unloaded)
- Can run HYBRID_TIERED with all local components without API calls

### 12.3 VRAM Budget Tables

**8 GB Tier — safe load sequences:**

```
Sequence A (LOCAL_STANDARD):
  1. Load PaddleOCR (~1.5 GB) → OCR all images → Unload (0 GB)
  2. Load MacBERT-base (~2 GB) → Correct → Unload (0 GB)
  3. Load BGE-M3 (~1.1 GB) → Dedup → Unload (0 GB)
  Peak: 2 GB

Sequence B (LOCAL_LLM):
  1. Load PaddleOCR (~1.5 GB) → OCR → Unload (0 GB)
  2. Load Qwen2.5-7B Q4 (~5 GB) → Correct → Unload (0 GB)
  Peak: 5 GB

Sequence C (HYBRID_TIERED):
  1. PaddleOCR → Unload
  2. MacBERT-base → Correct high/med confidence → Unload
  3. Qwen2.5-7B → Correct low confidence → Unload
  4. BGE-M3 → Dedup → Unload
  Peak: 5 GB (Qwen step)
```

**16 GB Tier — safe load sequences:**

```
Sequence A (LOCAL_STANDARD):
  1. PaddleOCR (~1.5 GB) → OCR → Unload
  2. MacBERT-large (~4 GB) + BGE-M3 (~1.1 GB) concurrent → ~5.1 GB
  Peak: 5.1 GB

Sequence B (LOCAL_LLM):
  1. PaddleOCR (~1.5 GB) → OCR → Unload
  2. Qwen2.5-14B Q4 (~10 GB) → Correct
  3. BGE-M3 (~1.1 GB) stays loaded → Dedup
  Peak: ~11.1 GB

Sequence C (HYBRID_TIERED, fully local):
  1. PaddleOCR → Unload
  2. MacBERT-large (~4 GB) → high/med confidence
  3. BGE-M3 loads concurrent (~1.1 GB) → stays resident
  4. Qwen2.5-14B (~10 GB) → low confidence → Unload
  Peak: ~11.1 GB — fits in 16 GB
  BGE-M3 stays loaded throughout batch for dedup
```

### 12.4 Tier-Aware Configuration Defaults

When `vram_tier` changes in settings, these config defaults should update automatically (user can override):

| Config Key | 8 GB default | 16 GB default |
|-----------|-------------|---------------|
| `local_llm_model` | `qwen2.5:7b-instruct-q4_K_M` | `qwen2.5:14b-instruct-q4_K_M` |
| `csc_model` | `macbert-base` | `macbert-large` |
| `embedding_resident` | `false` | `true` |
| `vram_budget_mb` | `7680` | `15360` |
| `recommended_pipeline_mode` | `HYBRID_TIERED` | `HYBRID_TIERED` or `LOCAL_LLM` |

---

*End of App Guidelines*
