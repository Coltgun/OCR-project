# OCR Guidelines: Simplified Chinese Pipeline Reference

> **Purpose:** This document is a technical reference for Cline to use when building, extending, or making decisions about the Simplified Chinese OCR post-processing pipeline. It covers each stage of the pipeline, the rationale for each approach, Chinese-specific nuances, library recommendations, model recommendations (local and via OpenRouter), and pipeline routing logic.

---

## Table of Contents

1. [Chinese OCR Fundamentals](#1-chinese-ocr-fundamentals)
2. [Stage 0: OCR Engine (PaddleOCR)](#2-stage-0-ocr-engine-paddleocr)
   - PP-OCRv4 vs PP-OCRv5
   - RapidOCR alternative
   - Image preprocessing
   - Reading order reconstruction
3. [Stage 1: Raw Text Cleanup](#3-stage-1-raw-text-cleanup)
4. [Stage 2: Error Detection & Correction](#4-stage-2-error-detection--correction)
   - 2A: Traditional (Rule/Dictionary-Based)
   - 2B: Hybrid (BERT-Based CSC)
   - 2C: Full LLM Correction
5. [Stage 3: Deduplication](#5-stage-3-deduplication)
   - 3A: Traditional (Exact + Near-Duplicate Hashing)
   - 3B: Semantic (Embedding-Based)
   - 3C: LLM Semantic Dedup
6. [Stage 4: Post-Normalization & Output Formatting](#6-stage-4-post-normalization--output-formatting)
7. [Pipeline Routing Logic](#7-pipeline-routing-logic)
8. [Hardware Context & Model Recommendations](#8-hardware-context--model-recommendations)
9. [Chinese-Specific Nuances & Pitfalls](#9-chinese-specific-nuances--pitfalls)
10. [Installation & Environment Setup](#10-installation--environment-setup)
11. [Library Quick Reference](#11-library-quick-reference)

---

## 1. Chinese OCR Fundamentals

### Why Chinese OCR is Harder Than Latin-Script OCR

- **No word delimiters.** Chinese text has no spaces between words — characters run together. This means you cannot use whitespace to delimit tokens. Segmentation is a separate step requiring NLP tools.
- **Character-level errors, not word-level.** A single misrecognized stroke changes a character entirely. OCR errors in Chinese are almost always **character substitutions** — insertions and deletions of whole characters are rare (unlike English OCR where letter-level insertions/deletions are common).
- **Visual character similarity (homoglyphs).** Many Chinese characters differ by a single stroke or radical: 己/已/巳, 土/士, 末/未, 人/入, 大/太/犬, 目/日, 田/由/甲, etc. OCR confusables are primarily **visually similar**, not phonetically.
- **Phonetic confusion (for typed or ASR-sourced text).** Homophone characters with the same pinyin: 的/地/得, 在/再, 他/她/它. Relevant if the source is partially typed or voice-to-text. For pure OCR output, visual similarity dominates.
- **Character set size.** GB2312 covers ~6,763 characters. GB18030/Unicode CJK adds many more. Rare characters may fall outside training sets.
- **Encoding issues.** Legacy documents may use GBK, GB2312, or Big5. Always normalize to UTF-8 before processing.
- **Mixed script.** Real-world documents often mix Chinese characters with Latin letters, Arabic numerals, full-width punctuation, and half-width punctuation. These require different handling.
- **Vertical text.** Some traditional layouts (books, newspapers) use vertical columns. PaddleOCR handles this but the reading order of lines may require reordering post-OCR.
- **Simplified vs. Traditional.** These are different character sets. Do not conflate them. Simplified Chinese (简体字) is used in mainland China. Traditional (繁體字) is used in Taiwan, Hong Kong. Explicitly configure OCR for Simplified.

---

## 2. Stage 0: OCR Engine (PaddleOCR)

### PP-OCRv4 vs PP-OCRv5 — Which to Use

**PP-OCRv5** (PaddleOCR 3.0+, released 2025):
- Uses PaddlePaddle 3.x framework
- Model format changed from `.pdmodel` to `.json` — breaks older deployment tools (OpenVINO, etc.)
- Achieves 94.5% accuracy on document parsing benchmarks (early 2026)
- Supports unified recognition of Simplified Chinese, Traditional Chinese, Pinyin, English, Japanese in a single model
- Requires `paddlepaddle-gpu>=3.0.0`
- **Recommended** for new projects — highest accuracy

**PP-OCRv4** (PaddleOCR 2.x):
- Uses PaddlePaddle 2.x — more stable, wider tool compatibility
- Still highly accurate for Simplified Chinese
- Use if you need OpenVINO or TensorRT deployment or have strict dependency constraints

**RapidOCR** — Alternative wrapper worth knowing:
- Wraps PaddleOCR models but runs inference via **ONNX Runtime** instead of PaddlePaddle
- Removes the PaddlePaddle framework as a dependency entirely
- Works on AMD GPUs (ROCm) and CPU-only systems — more portable
- Slightly lower peak accuracy than native PaddleOCR due to ONNX conversion, but negligible for most Chinese text
- Useful fallback if PaddlePaddle installation proves problematic
- Install: `pip install rapidocr-onnxruntime` or `rapidocr-paddle`
- GitHub: `RapidAI/RapidOCR`

**Recommendation:** Use PP-OCRv5 via native PaddlePaddle for GPU acceleration. Keep RapidOCR as a fallback option in the codebase, activated via config flag.

### Recommended: PaddleOCR (PP-OCRv5 / PP-OCRv4)

PaddleOCR is the primary OCR engine. It is fast, accurate, and runs fully locally on the RTX 4070.

**Key configuration notes:**

```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    lang='ch',                  # Simplified Chinese + English mixed
    use_angle_cls=True,         # Detect and correct rotated text
    use_gpu=True,               # Use CUDA (RTX 4070)
    det_model_dir='...',        # Optional: custom detection model path
    rec_model_dir='...',        # Optional: custom recognition model path
    cls_model_dir='...',
    show_log=False,
)
result = ocr.ocr('image.png', cls=True)
```

- `lang='ch'` enables the combined Simplified Chinese + English recognition model.
- `use_angle_cls=True` is important for scanned documents that may have rotated lines.
- PP-OCRv5 (PaddleOCR 3.0+) supports unified recognition of Simplified Chinese, Traditional Chinese, Pinyin, English, and Japanese in a single model.
- PP-OCRv5 requires `paddlepaddle-gpu>=3.0.0`. Model files are now `.json` format — do not attempt to use `.pdmodel` paths.
- If using PP-OCRv5 and getting `RuntimeError: A dependency error occurred during pipeline creation`, run: `pip install paddlex[ocr]`

### Output Format

PaddleOCR returns a list of `[bounding_box, (text, confidence_score)]` tuples per line. Preserve the confidence scores — they are used later in Stage 2 to flag low-confidence regions for more aggressive correction.

**Always retain:**
- The raw recognized text
- Per-line confidence score
- Bounding box coordinates (useful for reading-order reconstruction)

### Image Preprocessing (Before OCR)

For best results, preprocess images before passing to PaddleOCR:

1. **Resolution**: Minimum 150 DPI recommended; 300 DPI ideal for printed text. Scale up low-res images with `cv2.resize()` using INTER_CUBIC.
2. **Binarization**: For scanned documents, apply Otsu's thresholding or Sauvola adaptive thresholding. Avoid for photos with natural lighting.
3. **Deskewing**: Use OpenCV Hough line detection or `deskew` library to correct rotated scans. PaddleOCR handles mild rotation, but extreme angles (>15°) should be corrected first.
4. **Noise removal**: Morphological operations (erosion/dilation) to clean up salt-and-pepper noise. `cv2.fastNlMeansDenoisingColored()` for photographic noise.
5. **Contrast enhancement**: CLAHE (Contrast Limited Adaptive Histogram Equalization) for uneven lighting.
6. **Remove watermarks/stamps**: Skewed or angled text overlays can be detected by computing the angle of bounding boxes and removing those with high inclination angles relative to horizontal.

### Reading Order Reconstruction

PaddleOCR returns lines in detection order, which may not be reading order for multi-column layouts. For multi-column documents:
- Sort bounding boxes left-to-right, then top-to-bottom within columns.
- Use `x_center` and `y_center` of bounding boxes to cluster into columns (K-means or simple threshold-based).
- For vertical text (traditional layout), lines should be read right-to-left, top-to-bottom within each column.

---

## 3. Stage 1: Raw Text Cleanup

**This entire stage runs locally. It is fast, deterministic, and purely rule-based. No model inference needed.**

### 1A: Encoding Normalization

```python
import unicodedata

def normalize_encoding(text: str) -> str:
    # Normalize to NFC (Canonical Decomposition, Canonical Composition)
    # This ensures consistent Unicode representation
    return unicodedata.normalize('NFC', text)
```

- Always apply NFC normalization first.
- If input text was decoded from GBK or GB2312, ensure it has been properly decoded to a Python `str` (UTF-8 internally) before processing.

### 1B: Full-Width / Half-Width Normalization

Chinese documents frequently mix full-width (全角) and half-width (半角) characters. OCR may introduce inconsistencies.

**Full-width characters** occupy 2 bytes in legacy encodings and appear as wide characters: `Ａ`, `１`, `（`, `，`
**Half-width characters** are standard ASCII equivalents: `A`, `1`, `(`, `,`

```python
import unicodedata

def normalize_fullwidth(text: str) -> str:
    result = []
    for char in text:
        cp = ord(char)
        # Full-width ASCII variants (FF01-FF5E) → ASCII (0021-007E)
        if 0xFF01 <= cp <= 0xFF5E:
            result.append(chr(cp - 0xFEE0))
        # Full-width space (　, U+3000) → regular space
        elif cp == 0x3000:
            result.append(' ')
        else:
            result.append(char)
    return ''.join(result)
```

**Important:** Chinese punctuation should NOT be converted to half-width. Only convert alphanumeric characters and certain symbols. Specifically:
- Convert: `Ａ-Ｚ`, `ａ-ｚ`, `０-９`, full-width Latin punctuation
- Keep as-is: `，` (Chinese comma), `。` (Chinese period), `「」`, `《》`, `【】`, `—`, `…`, etc.

A safer approach is to only normalize Latin letters and digits, leaving everything else alone.

### 1C: Whitespace Cleanup

Chinese text **does not use spaces between words**. Any space between CJK characters in OCR output is almost certainly an OCR artifact and should be removed.

```python
import re

def cleanup_cjk_spaces(text: str) -> str:
    # Remove spaces between CJK characters (U+4E00–U+9FFF, U+3400–U+4DBF, etc.)
    # This regex removes spaces that appear between two CJK characters
    cjk = r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u309f\u30a0-\u30ff]'
    pattern = rf'({cjk})\s+({cjk})'
    # Must apply repeatedly until stable (handles multiple spaces)
    while True:
        new_text = re.sub(pattern, r'\1\2', text)
        if new_text == text:
            break
        text = new_text
    return text
```

**Do NOT** remove spaces between:
- CJK characters and Latin/numeric characters (e.g., `Python 3.9` embedded in Chinese text)
- At the beginning or end of lines/paragraphs
- Between paragraphs

### 1D: Punctuation Normalization

Chinese uses specific punctuation that OCR may misidentify:

| Correct | Common OCR Error | Fix |
|---------|-----------------|-----|
| `，` (U+FF0C) | `,` (comma) | Map based on context |
| `。` (U+3002) | `.` (period) | Map based on context |
| `、` (U+3001) | `、` (usually fine) | — |
| `；` (U+FF1B) | `;` | Context-dependent |
| `：` (U+FF1A) | `:` | Context-dependent |
| `？` (U+FF1F) | `?` | Context-dependent |
| `！` (U+FF01) | `!` | Context-dependent |
| `"` / `"` | `"` (straight quotes) | Pair-match to restore |
| `'` / `'` | `'` (straight apostrophe) | Pair-match to restore |
| `《》` | `<>` or other brackets | Regex fix |
| `【】` | `[]` | Regex fix |
| `——` (em dash) | `-` or `--` | Pattern fix |
| `……` (ellipsis) | `...` | Pattern fix |

**Strategy:** Apply punctuation normalization after full-width normalization. Be conservative — only map characters when the surrounding context is entirely Chinese.

```python
def normalize_punctuation(text: str) -> str:
    # Only apply when surrounded by Chinese context
    # Replace straight quotes with Chinese curly quotes using pair-matching
    # Simple pattern: first unmatched " → 「, second → 」 (or use " " style)
    text = text.replace('...', '……')
    text = text.replace('--', '——')
    # Add domain-specific rules as needed
    return text
```

### 1E: Line Break and Paragraph Reconstruction

OCR splits text into lines. For coherent paragraphs:

1. **Concatenate lines** from the same text region (use bounding box Y coordinates).
2. **Detect paragraph breaks**: A paragraph typically ends with `。` `！` `？`. A new paragraph usually has indentation in the source, visible as a gap in Y coordinates between bounding boxes.
3. **Handle hyphenation artifacts**: Chinese does not hyphenate, so cross-line breaks in Chinese text just need concatenation without any special character.
4. **Remove running headers/footers**: Text appearing consistently at the top or bottom of multiple pages (same Y range, similar content) should be identified and optionally removed or separated.

### 1F: Garbage Text Filtering

Low-confidence OCR regions often produce character strings that are not valid Chinese. Filter using:
- **Confidence threshold**: Drop lines where PaddleOCR confidence < 0.5 (configurable). Flag 0.5–0.7 for correction.
- **Character validity**: If a line contains >40% characters outside the CJK Unicode blocks and common punctuation, flag it.
- **Length filters**: Very short fragments (1–2 characters) that are isolated may be OCR artifacts from decorative elements.
- **Repeated character filter**: A string of the same character repeated many times (`————————`) is likely a border or separator — handle appropriately.

---

## 4. Stage 2: Error Detection & Correction

Chinese Spelling Correction (CSC) is a well-studied NLP task. For OCR-sourced errors, the dominant error type is **visual character substitution** — one character replaced by a visually similar one.

The three sub-stages below are ordered from fastest/cheapest to most capable. The pipeline should be designed to apply them in sequence, with each stage handling progressively harder cases.

---

### 2A: Traditional Error Correction (Local, No Model Required)

**When to use:** Always run this first. It is fast (milliseconds), requires no GPU, and catches the most systematic errors.

#### 2A-1: Confusion Set / Character Substitution Table

Maintain a **Chinese OCR confusion table** — a mapping of common OCR character misrecognitions. This is the most reliable correction for systematic errors.

Build from:
- Known PaddleOCR common errors (empirically derived from your own data)
- Visually similar character pairs from Unicode confusables + CJK-specific lists
- Domain-specific patterns (medical, legal, etc.)

Common OCR confusion pairs in Simplified Chinese (partial list):

```python
# Visual similarity confusables (common in printed Chinese OCR)
OCR_CONFUSION_TABLE = {
    '己': ['已', '巳'],
    '土': ['士'],
    '末': ['未'],
    '人': ['入'],
    '大': ['太', '犬'],
    '目': ['日', '曰'],
    '田': ['由', '甲'],
    '口': ['囗'],
    '力': ['刀'],
    '八': ['入'],
    '0': ['○', '〇'],  # Numeral zero vs Chinese circle
    'O': ['○'],
    '1': ['l', 'I', '｜'],
    # Add more from empirical error analysis of your specific documents
}
```

**How to use:** For each character in the OCR output, look it up in the confusion table. If found, use dictionary lookup and context (n-gram language model or word segmentation) to decide if the substitute is more likely.

#### 2A-2: Dictionary-Based Validation

Use a Chinese word dictionary to validate segmented words:

```python
import jieba

# After segmentation, check each segment against a dictionary
# Flag segments that are not valid Chinese words or proper nouns
```

**Libraries:**
- `jieba` — fast, widely used Chinese word segmentation. Good default.
- `pkuseg` — higher accuracy, multi-domain models (web, medicine, tourism, news). Better for domain-specific text.
- `HanLP` — comprehensive NLP suite, supports segmentation, POS tagging, NER. Higher resource usage.

**Recommendation:** Use `jieba` for general text; switch to `pkuseg` if the document domain is medical, legal, or other specialized fields.

#### 2A-3: N-gram Language Model Scoring

A character-level trigram or 4-gram language model trained on Chinese text can score candidate corrections:

- For each flagged character (low confidence or in confusion table), generate candidates.
- Score each candidate using the LM based on surrounding context.
- Select the highest-scoring candidate that is also a valid character.

**Libraries:**
- `kenlm` — fast n-gram LM, supports Chinese. Train on a Chinese corpus (e.g., Chinese Wikipedia, news corpus).
- Character perplexity: lower perplexity = more likely text.

**When n-gram LMs suffice:** Single-character substitutions in otherwise clean text. Works well for systematic errors that repeat.

#### 2A-4: Rule-Based Pattern Corrections

Some errors are consistent patterns fixable with regex:

```python
import re

def apply_pattern_corrections(text: str) -> str:
    # Fix common OCR pattern errors
    # e.g., 'l' (lowercase L) misread as '1' (one) in mixed context
    # e.g., spacing artifacts around punctuation
    text = re.sub(r'(\d)\s*[。]\s*(\d)', r'\1.\2', text)  # Decimal points
    # Add domain-specific patterns
    return text
```

---

### 2B: Hybrid Correction (BERT-Based CSC — Local)

**When to use:** After Stage 2A, for text that is still flagged as potentially erroneous (low OCR confidence regions, segments not found in dictionary, characters that matched confusion table but context was ambiguous).

**This runs locally on the RTX 4070.**

#### What Is Chinese Spelling Correction (CSC)?

CSC models are fine-tuned BERT/RoBERTa models specifically trained to detect and correct Chinese character errors. They operate at the character level, making them ideal for OCR errors. They use:
- **Detector**: Identifies which characters are likely wrong (binary classification per character).
- **Corrector**: For each flagged character, selects the correct replacement from a confusion set.

The Detector-Corrector (D-C) architecture is the dominant paradigm. Notable examples:
- **Soft-Masked BERT** (Zhang et al., 2020): Uses a Bi-GRU detector with soft masking, feeding error probability into the corrector.
- **EGCM** (Error-Guided Correction Model): Zero-shot error detection guiding the correction model. State-of-the-art on standard CSC benchmarks.
- **BERT + Phonetic Pre-training**: Incorporates pinyin information to improve phonetic confusion correction.

#### Recommended Local Models for CSC

**Option 1: Use a fine-tuned Chinese BERT CSC model from HuggingFace**

Look for models fine-tuned on SIGHAN benchmarks (SIGHAN13/14/15 are standard CSC evaluation sets):

```
Search HuggingFace for: "chinese spelling correction" OR "CSC" OR "chinese-roberta-wwm"
Notable: shibing624/pycorrector (backs the pycorrector library)
```

**Option 2: `pycorrector` library** (recommended as starting point)

`pycorrector` is a Python library that wraps multiple Chinese text correction backends:

```python
import pycorrector

# Default (KenLM n-gram based)
corrected_sent, detail = pycorrector.correct('少先队员因该为老人让坐')

# MacBERT-based (higher quality)
from pycorrector.macbert.macbert_corrector import MacBertCorrector
m = MacBertCorrector()
result = m.correct_batch(['文本一', '文本二'])

# Supports: KenLM, BERT, MacBERT, T5, GPT, Ernie
```

**Recommended pycorrector backend for local use:** `MacBERT` — it was specifically pre-trained with OCR and spelling errors in the masked language model objective, making it excellent for CSC tasks. VRAM usage: ~2-4 GB for the base model.

**Option 3: `ltp` (Language Technology Platform)** — Harbin Institute of Technology's Chinese NLP suite. Provides segmentation, POS tagging, NER, and dependency parsing alongside correction.

#### VRAM Budget for Stage 2B on RTX 4070 Laptop (8 GB VRAM)

| Model | VRAM | Speed |
|-------|------|-------|
| MacBERT-base CSC | ~2 GB | Fast |
| MacBERT-large CSC | ~4 GB | Moderate |
| Chinese RoBERTa-base | ~2 GB | Fast |
| Qwen2.5-1.5B (small LLM, Stage 2C light) | ~4 GB | Moderate |

Since PaddleOCR also uses VRAM (approximately 1–2 GB for detection + recognition models), budget carefully on 8 GB VRAM. The required approach is to run OCR first, **explicitly unload the OCR model from GPU** before loading the CSC model. Do not hold both in VRAM simultaneously.

#### Hybrid Pipeline (BERT + LLM Verifier Pattern)

Research shows that combining a BERT-based corrector with an LLM verifier (ACI pattern) outperforms either alone:

1. **BERT corrector** makes corrections → fast, parallelizable
2. **LLM verifier** checks the correction → confirms or provides alternative

This is particularly useful because BERT-CSC models tend to **over-correct** (modify correct characters). The LLM verifier catches false positives.

For local use, the LLM verifier can be a small local model (see Stage 2C local options).

---

### 2C: Full LLM Correction

**When to use:**
- Text has complex errors that pattern matching and BERT models miss
- Source documents have domain-specific terminology requiring broad knowledge
- You are in an "online mode" pipeline (all steps delegated to API)
- OCR confidence was very low across large portions of the document

**Key principle for pipeline design:** If using an online LLM for correction (OpenRouter), it should handle the entire correction pass for that document segment. Do not split a document segment between a slow local step and a fast online step — the latency of invoking the online API means you should batch corrections together into a single call.

#### Prompt Design for Chinese OCR Correction

The LLM must:
1. Correct character-level OCR errors (visual substitutions)
2. NOT hallucinate — stay close to the original text
3. NOT translate or paraphrase — only correct errors
4. Preserve all punctuation and structure
5. Return output in the same format as input

**Anti-hallucination constraints are critical.** LLMs have a tendency to "improve" text beyond correcting errors. Enforce strict constraints:

```
System prompt:
你是一个专业的中文OCR后处理系统。你的唯一任务是更正OCR识别错误。
规则：
1. 只更正明显的字符识别错误（形近字替换）
2. 不得改写、翻译、润色或扩充原文
3. 不得添加或删除完整的词语或句子
4. 保持所有标点符号、换行符和格式
5. 如果一段文字看起来正确，原样输出，不做任何修改
6. 输出修正后的文本，格式与输入完全一致

User:
请更正以下OCR识别的中文文本中的字符错误：
[OCR_TEXT]
```

**Chunking strategy:** Do not send entire documents at once. Chunk by:
- Paragraph boundaries
- Maximum ~800-1200 Chinese characters per chunk (fits well in context without padding waste)
- Include 1-2 sentences of overlap between chunks for context continuity

#### Local LLM Correction (Qwen series — recommended)

For purely local correction without API calls:

**Qwen2.5-7B-Instruct** (Q4_K_M quantized via Ollama or llama.cpp):
- VRAM: ~5-6 GB at Q4_K_M
- Native Chinese training data; strong Chinese language understanding
- Leaves ~10 GB VRAM free for other tasks
- Speed: ~20-30 tokens/sec on RTX 4070 — acceptable for moderate volumes

**Qwen3.5-9B** (Q4 quantized):
- VRAM: ~5-6 GB at INT4
- Better reasoning than Qwen2.5-7B
- Recommended for correction tasks requiring more contextual judgment

**Qwen2.5-14B** (Q4_K_M):
- VRAM: ~10-11 GB at Q4_K_M — **does not fit on 8 GB VRAM**. Would require heavy CPU offload, making it impractically slow for this pipeline.
- Not recommended for local use on this system.

**Qwen3.5-27B** / **Qwen2.5-32B** — not viable on 8 GB VRAM under any quantization.

**Recommendation for local LLM correction: Qwen2.5-7B or Qwen3.5-9B at Q4_K_M via Ollama or llama.cpp**

> **Note:** With only 8 GB VRAM, the local LLM correction tier (Stage 2C) is significantly constrained. The quality ceiling locally is a 7–9B parameter model. For demanding correction quality, the online (OpenRouter) pipeline is strongly preferred. This is a good use case for the hybrid routing strategy — use local for high-confidence text and defer to online for low-confidence regions.

#### OpenRouter LLM Correction

When using OpenRouter for correction, the entire post-OCR pipeline for that batch should be online (not just the correction step).

**Best value/quality options for Chinese text on OpenRouter (as of 2026):**

| Model | Input $/M | Output $/M | Chinese Quality | Notes |
|-------|-----------|------------|-----------------|-------|
| `deepseek/deepseek-v3.2` | $0.25 | $0.38 | Excellent | ~90% of frontier quality at 1/50th cost; native Chinese training |
| `qwen/qwen3.5-27b` | ~$0.20 | ~$1.56 | Excellent | Alibaba's own model; native Chinese |
| `qwen/qwen3-235b-a22b` | $0.07 | $0.10 | Outstanding | MoE, very cheap per token; top quality |
| `qwen/qwen3.5-flash` | $0.065 | ~$0.15 | Very Good | Fastest option; good for high volume |
| `google/gemini-3.1-flash-lite` | $0.25 | $1.50 | Good | Fast; good multilingual |
| `anthropic/claude-sonnet-4-6` | ~$3 | ~$15 | Excellent | Premium; use only if quality demands it |

**Strong recommendation for OCR correction on OpenRouter: `deepseek/deepseek-v3.2`**
- DeepSeek is a Chinese AI company; their models have exceptional native Chinese capability
- Cost is negligible for OCR correction tasks (short prompts, moderate outputs)
- Comparable to GPT-4-class for Chinese NLP at a fraction of the cost

**For very high volume / budget-conscious: `qwen/qwen3-235b-a22b`**
- MoE architecture — only 22B active parameters despite 235B total
- $0.071 input / $0.10 output — extraordinarily cheap
- Strong Chinese language capability (Alibaba's flagship)

**Anti-pattern to avoid:** Do NOT use GPT-4o or Claude for bulk Chinese OCR correction unless the content is highly complex and quality is critical. The cost differential is extreme for what is fundamentally a constrained correction task.

---

## 5. Stage 3: Deduplication

Deduplication is relevant when processing batches of documents, or when the same source document may have been processed multiple times (e.g., re-scanning), or when aggregating OCR results from multiple passes.

There are two axes of deduplication:
- **Exact/near-exact**: Identical or nearly identical text strings
- **Semantic**: Text that says the same thing differently (paraphrases, reordered content)

---

### 3A: Traditional Deduplication (Local, No Model)

**Always run this first. It is O(n) or O(n log n), very fast, requires no GPU.**

#### Exact Deduplication

```python
seen = set()
unique_texts = []
for text in texts:
    normalized = text.strip()
    if normalized not in seen:
        seen.add(normalized)
        unique_texts.append(text)
```

#### MinHash / LSH (Near-Duplicate Detection)

MinHash + Locality-Sensitive Hashing finds documents that are largely similar (e.g., 90%+ character overlap).

```python
from datasketch import MinHash, MinHashLSH

def get_minhash(text: str, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    # For Chinese: use character n-grams (not word-level, since no spaces)
    for i in range(len(text) - 2):
        ngram = text[i:i+3]  # Character trigrams
        m.update(ngram.encode('utf-8'))
    return m

lsh = MinHashLSH(threshold=0.85, num_perm=128)
# Insert documents, then query for near-duplicates
```

**Key for Chinese text:** Use **character n-grams** (bigrams or trigrams) as shingles, not word-level n-grams. Since there are no word delimiters, character n-grams are the correct atomic unit for MinHash.

#### SimHash (Fingerprint-Based)

SimHash generates a binary fingerprint per document; Hamming distance measures similarity. Effective for large-scale near-duplicate detection.

```python
# Use: simhash library, or custom implementation
from simhash import Simhash

def get_simhash(text: str) -> Simhash:
    # Tokenize with jieba first for better feature extraction
    import jieba
    features = list(jieba.cut(text))
    return Simhash(features)

# Two documents with Hamming distance ≤ 3 are considered near-duplicates
```

**Recommendation:** MinHash LSH for datasets >10K documents (better recall); SimHash for moderate datasets (simpler implementation).

**Chinese-specific SimHash improvement:** Use TF-IDF weighted character features combined with word-level features from jieba segmentation. Synonym replacement using CiLin (同义词词林) thesaurus can improve semantic coverage before fingerprinting.

---

### 3B: Semantic Deduplication (Embedding-Based — Local)

Semantic dedup catches cases where text is paraphrased or reordered but conveys the same content. This is less common for OCR post-processing (where you want to keep all content) but useful when aggregating results from multiple document sources.

#### Recommended: SemHash + BGE-M3

```python
from semhash import SemHash
from sentence_transformers import SentenceTransformer

# Load BGE-M3 — excellent Chinese + multilingual support, only ~1 GB VRAM
model = SentenceTransformer('BAAI/bge-m3')

semhash = SemHash.from_records(records=texts, model=model)
result = semhash.self_deduplicate(threshold=0.92)
deduplicated = result.selected
```

**Why BGE-M3:**
- Developed by BAAI (Beijing Academy of AI) — specifically strong on Chinese
- Only ~1 GB VRAM in FP16 — negligible on RTX 4070
- Supports dense retrieval, sparse retrieval (BM25-style), and multi-vector retrieval
- State-of-the-art on Chinese MTEB benchmarks
- Works excellently for Chinese text similarity

**Alternative embeddings for Chinese:**
| Model | VRAM | Chinese Quality | Notes |
|-------|------|-----------------|-------|
| `BAAI/bge-m3` | ~1 GB | Excellent | Recommended default |
| `BAAI/bge-large-zh-v1.5` | ~1.3 GB | Excellent | Chinese-specific |
| `BAAI/bge-base-zh-v1.5` | ~0.5 GB | Very Good | Faster, smaller |
| `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | ~1 GB | Good | Broader multilingual |

**Threshold guidance:**
- `0.95+` — essentially exact character-level matches only
- `0.90–0.95` — near-paraphrase; safe for aggressive dedup of redundant content
- `0.85–0.90` — thematic similarity; may remove distinct but related content (use carefully)
- `<0.85` — not recommended for deduplication; will remove unique content

#### ANN Backend for Scale

For large datasets (100K+ documents), use FAISS as the ANN backend:

```python
from semhash import SemHash
from vicinity import Backend

semhash = SemHash.from_records(records=texts, model=model, ann_backend=Backend.FAISS, nlist=100)
```

---

### 3C: LLM-Based Semantic Deduplication

**When to use:** Only for small batches where semantic judgment is critical — e.g., determining if two passages are substantively duplicates despite different wording. LLM dedup is expensive and slow at scale.

**Online approach (OpenRouter):**

```python
prompt = """
以下两段中文文本是否表达了相同的核心内容？
仅回答"是"或"否"，不需要解释。

文本A：{text_a}
文本B：{text_b}
"""
```

Use `deepseek/deepseek-v3.2` for this task — fast and cheap.

**Local approach:** Use Qwen2.5-7B or Qwen3.5-9B local model with a similar prompt. Reserve for batches where embedding similarity is in the ambiguous range (0.85–0.92).

**Hybrid strategy (recommended):**
1. Embedding-based dedup first to find candidate pairs (similarity > 0.85)
2. LLM judgment only for ambiguous pairs in the 0.85–0.92 range
3. Clear duplicates (>0.95) are handled directly without LLM

---

## 6. Stage 4: Post-Normalization & Output Formatting

After correction and dedup, apply final normalization before output.

### Output Text Normalization

```python
def final_normalize(text: str) -> str:
    # Remove leading/trailing whitespace per paragraph
    paragraphs = text.split('\n')
    paragraphs = [p.strip() for p in paragraphs]
    
    # Remove empty paragraphs (but preserve intentional double newlines)
    # Be conservative — don't collapse all blank lines
    
    # Ensure consistent paragraph indentation if needed
    # Chinese formal text often indents 2 characters (两格缩进)
    
    return '\n'.join(paragraphs)
```

### Number and Mixed-Script Normalization

- Arabic numerals in Chinese text: keep as-is unless source specifies Chinese numeral format
- Units: normalize spacing between numbers and units (e.g., `5 kg` vs `5kg`)
- Dates: normalize to consistent format if required by downstream application

### Output Format Options

- **Plain text**: Simple UTF-8 encoded `.txt`
- **JSON with metadata**: Include original bounding boxes, confidence scores, correction log
- **Structured segments**: Preserve paragraph breaks as semantic units for downstream RAG or indexing

---

## 7. Pipeline Routing Logic

### Core Principle

> Stages that use called LLMs (API) should be grouped together. If you use an online model for one step, route the entire processing of that document/batch online. Do not mix slow local model inference with fast API calls in the same batch — the API's speed advantage is wasted.

### Pipeline A: Full Local (Default)

**Use when:** Privacy requirements, no internet, testing, or bulk processing where cost is a concern.

```
Image → Preprocessing → PaddleOCR → Stage 1 (Cleanup) → Stage 2A (Rules/Dictionary) 
     → Stage 2B (MacBERT/pycorrector local) → Stage 3A (MinHash) 
     → Stage 3B (BGE-M3 embeddings) → Stage 4 (Output)
```

**VRAM usage timeline:**
- PaddleOCR: ~2 GB VRAM → release after OCR
- MacBERT CSC: ~2-4 GB VRAM → release after correction
- BGE-M3: ~1 GB VRAM → keep loaded if processing batches
- Total peak: ~6 GB — fits within 8 GB, but unload PaddleOCR before loading the CSC model

### Pipeline B: Local OCR + Online Post-Processing

**Use when:** Quality is paramount; document complexity warrants LLM correction; you have API access.

```
Image → Preprocessing → PaddleOCR [LOCAL] → Stage 1 (Cleanup) [LOCAL]
     → Stage 2A (Rules) [LOCAL]
     → [SWITCH TO ONLINE]
     → Stage 2C (DeepSeek V3.2 correction) [ONLINE]
     → Stage 3A (MinHash) [LOCAL — fast, no model needed]
     → Stage 3B (BGE-M3 embeddings) [LOCAL]
     → [ONLINE if needed] Stage 3C (LLM dedup judgment) [ONLINE]
     → Stage 4 (Output)
```

**Rationale:** PaddleOCR is fast and accurate locally; the network round-trip for image-based OCR via API would be slow. Stage 1 cleanup is trivially fast. Once we enter LLM territory, batch into a single online call.

### Pipeline C: Hybrid (Tiered by Confidence)

**Use when:** Most text is high-confidence but some regions are problematic.

```
Image → PaddleOCR → Stage 1 Cleanup
     → Split by confidence:
         HIGH (>0.85): Stage 2A only → Stage 3A → Output
         MED (0.5-0.85): Stage 2A + Stage 2B (local BERT) → Stage 3A/3B → Output  
         LOW (<0.5): Stage 2A + Stage 2C (LLM, online or local 14B) → Stage 3A/3B → Output
```

### Decision Flowchart

```
Is this a single document or batch?
├── Single document, quality critical → Pipeline B (online)
├── Single document, privacy/offline → Pipeline A (full local)
└── Batch processing →
    ├── Large batch (>1000 docs), cost sensitive → Pipeline A
    ├── Large batch, quality critical → Pipeline B with batched API calls
    └── Mixed quality → Pipeline C (tiered by confidence)

Is any OCR confidence score <0.5?
├── Yes → flag for Stage 2C (LLM correction)
└── No → Stage 2A + 2B may suffice

Is this a dedup-heavy use case (aggregating many sources)?
├── Yes → Run Stage 3B (embeddings) always
└── No (single-pass OCR) → Stage 3A (exact/near-exact) is usually enough
```

---

## 8. Hardware Context & Model Recommendations

**System:** RTX 4070 Laptop GPU (8 GB VRAM), i7-13700HX, 32 GB RAM
**Supported VRAM tiers:** 8 GB (current) and 16 GB (future upgrade / other users) — see Tier System below.

---

### VRAM Tier System

The app and its guidelines support two explicit VRAM tiers. Tier selection drives model defaults, maximum model sizes, and safe concurrent loading rules. Set `vram_tier` in `config.json`.

| Tier | VRAM | Target hardware | Budget (safe) |
|------|------|-----------------|---------------|
| `8gb` | 8 GB | RTX 4070 Laptop, RTX 4060, RTX 3070 | 7,680 MB |
| `16gb` | 16 GB | RTX 4080, RTX 4070 Ti, RTX 3080 16GB | 15,360 MB |

---

### VRAM Budget Reference — Both Tiers

| Component | VRAM | 8 GB Tier | 16 GB Tier |
|-----------|------|-----------|------------|
| PaddleOCR PP-OCRv5 (det+rec+cls) | ~1.5 GB | ✓ | ✓ |
| MacBERT-base CSC | ~2 GB | ✓ preferred | ✓ |
| MacBERT-large CSC | ~4 GB | ⚠ unload OCR first | ✓ preferred |
| BGE-M3 FP16 | ~1.1 GB | ✓ (unload after use) | ✓ (can stay resident) |
| Qwen2.5-7B Q4_K_M | ~5 GB | ✓ (after OCR unloaded) | ✓ |
| Qwen3.5-9B INT4 | ~5–6 GB | ✓ (after OCR unloaded) | ✓ |
| Qwen2.5-14B Q4_K_M | ~10 GB | ✗ exceeds 8 GB | ✓ (after OCR unloaded, ~6 GB headroom) |
| Qwen3.5-27B Q4_K_M | ~15–17 GB | ✗ not viable | ⚠ tight, monitor KV cache |

**Inference speeds — RTX 4070 class (verified benchmarks):**
| Model | Tokens/sec |
|-------|------------|
| Qwen2.5-7B Q4_K_M | ~52 tok/sec |
| Qwen3.5-9B INT4 | ~40–48 tok/sec |
| Qwen2.5-14B Q4_K_M | ~33 tok/sec (RTX 4070 12GB ref) |

---

### Safe Concurrent Combos — 8 GB Tier

- PaddleOCR + MacBERT-base = ~3.5 GB ✓
- PaddleOCR + BGE-M3 = ~2.6 GB ✓
- MacBERT-base + BGE-M3 (OCR unloaded) = ~3.1 GB ✓
- Qwen2.5-7B Q4 alone (after OCR unloaded) = ~5 GB ✓ (~2.7 GB headroom)
- Qwen3.5-9B INT4 alone (after OCR unloaded) = ~5.5 GB ✓
- Qwen2.5-7B Q4 + BGE-M3 (OCR unloaded) = ~6.1 GB ✓ (tight — monitor)

**Hard limits (8 GB):**
- Do NOT hold PaddleOCR + any 7B+ LLM simultaneously — will OOM
- Qwen2.5-14B never fits — do not attempt, even with offload (will be impractically slow)
- MacBERT-large alone (4 GB) is fine after OCR unloaded; do not combine with LLM on 8 GB

### Safe Concurrent Combos — 16 GB Tier

- MacBERT-large + BGE-M3 (OCR unloaded) = ~5.1 GB ✓ (BGE-M3 can stay resident)
- Qwen2.5-14B Q4 + BGE-M3 (OCR unloaded) = ~11.1 GB ✓ (~4.2 GB for KV cache)
- MacBERT-large + Qwen2.5-14B Q4 (sequential, OCR unloaded): do NOT run concurrently = ~14 GB if both loaded
- PaddleOCR + BGE-M3 concurrent = ~2.6 GB ✓ (plenty of headroom on 16 GB)

**16 GB tier additional capabilities over 8 GB:**
- BGE-M3 can remain loaded throughout an entire batch (no per-batch unload/reload cycle)
- MacBERT-large runs without having to unload anything first after OCR phase
- Qwen2.5-14B fits comfortably — ~33 tok/sec provides good throughput for correction tasks
- HYBRID_TIERED mode can run fully local (all tiers covered by local models) without API fallback
- Full LOCAL_LLM pipeline with 14B model is practical (~33 tok/sec, well above usability threshold)

### Local Model Serving

**Recommended: Ollama** for managing local models

```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
ollama pull qwen2.5:7b-instruct-q4_K_M
```

Alternatively, **llama.cpp** directly or **LM Studio** for GUI management.

**For Python integration:**

```python
import ollama

response = ollama.chat(
    model='qwen2.5:14b-instruct-q4_K_M',
    messages=[
        {'role': 'system', 'content': CORRECTION_SYSTEM_PROMPT},
        {'role': 'user', 'content': f'请更正以下OCR文本：\n{ocr_text}'}
    ]
)
corrected = response['message']['content']
```

### Local Model Recommendation Summary

| Task | 8 GB Tier | 16 GB Tier |
|------|-----------|------------|
| CSC (BERT) | `MacBERT-base` (~2 GB) | `MacBERT-large` (~4 GB) |
| LLM correction (quality) | `Qwen3.5-9B INT4` (~5.5 GB) | `Qwen2.5-14B Q4_K_M` (~10 GB) |
| LLM correction (fast) | `Qwen2.5-7B Q4_K_M` (~5 GB) | `Qwen2.5-7B Q4_K_M` (overkill; use 14B) |
| Embeddings | `BGE-M3` FP16 (~1.1 GB, unload after) | `BGE-M3` FP16 (keep resident) |
| Dedup LLM judge | `Qwen2.5-7B Q4_K_M` (shared slot) | `Qwen2.5-14B Q4_K_M` (shared) |

**Config key:** `vram_tier: "8gb"` or `"16gb"` — the app must read this and select defaults automatically. Never hardcode model names outside of `config.json` defaults.

### OpenRouter Model Recommendation Summary

| Task | Recommended Model | Cost Notes |
|------|------------------|-----------|
| Full LLM correction | `deepseek/deepseek-v3.2` | $0.25/$0.38 per M tokens; best value |
| High-volume cheap correction | `qwen/qwen3-235b-a22b` | $0.07/$0.10 per M; MoE efficiency |
| Fast/cheap batch correction | `qwen/qwen3.5-flash` | $0.065/M; good for simple errors |
| Premium quality (complex docs) | `anthropic/claude-sonnet-4-6` | ~$3/$15; only if truly needed |
| Dedup judgment | `deepseek/deepseek-v3.2` | Same model; very cheap for binary tasks |

---

## 9. Chinese-Specific Nuances & Pitfalls

### 9.1 Do Not Segment Before Cleanup

Word segmentation (jieba/pkuseg) must happen AFTER encoding normalization and whitespace cleanup. Segmenters are sensitive to encoding artifacts and spurious spaces.

### 9.2 OCR Error Types in Chinese — Priority Order

1. **Visual substitution** (most common): OCR misreads a stroke → different character. e.g., 土→士, 末→未, 己→已.
2. **Radical confusion**: Characters sharing a radical: 情/清/请/晴 — all use 青 as phonetic component.
3. **Character merging**: OCR treats two adjacent characters as one (rare in printed text).
4. **Character splitting**: OCR splits one character into two components (rare in printed text).
5. **Number/Latin confusion**: `0`/`O`, `1`/`l`/`I`, `5`/`S` — especially in mixed-script documents.

### 9.3 Confidence Score Calibration

PaddleOCR confidence scores are not perfectly calibrated. Empirically:
- Score > 0.90: Usually correct
- Score 0.70–0.90: Occasionally wrong; run through Stage 2A/2B
- Score 0.50–0.70: Frequently wrong; run through Stage 2B/2C
- Score < 0.50: Often garbage; consider whether to include at all

Build a calibration profile for your specific document type (scanned books, photos, receipts, etc.) by manually checking a sample.

### 9.4 Do Not Over-Correct

Over-correction is a known problem in CSC models. A model may "correct" a correct character to a wrong one. Mitigation:
- Only correct positions flagged by the detector (not all characters)
- Use an LLM verifier step after BERT correction
- Set a conservative correction threshold — require confidence > 0.7 in the correction before applying
- Log all corrections with original text for review

### 9.5 Simplified ↔ Traditional Mixing

If source documents mix Simplified and Traditional Chinese (e.g., Hong Kong documents, older PRC documents), do not blindly convert Traditional to Simplified or vice versa. Use `opencc` if conversion is needed and the source language is known:

```python
import opencc
converter = opencc.OpenCC('t2s')  # Traditional to Simplified
simplified = converter.convert(traditional_text)
```

### 9.6 Names, Places, and Proper Nouns

Named entities (人名, 地名, 机构名) are especially vulnerable to OCR errors because they may not appear in dictionaries. Errors in names are also especially harmful. Use NER (Named Entity Recognition) to identify named entities and handle them separately:

- Flag named entities for human review rather than automatic correction
- Or use a domain-specific gazetteer (list of known names) for lookup
- `HanLP` provides strong Chinese NER capabilities

### 9.7 Numbers and Dates

Chinese numbers mix Arabic numerals, Chinese number words (一二三…, 十百千万亿), and mixed forms (2024年3月15日). Do not normalize these unless specifically required — preserving source format is safer.

### 9.8 Classical Chinese vs Modern Chinese

Classical Chinese (文言文) has very different vocabulary and grammar. Standard CSC models trained on modern text will perform poorly on classical texts. If processing classical texts, specialized models or rule sets are needed.

### 9.9 Encoding: UTF-8 Only in Pipeline

Never pass bytes through the pipeline — always decode to Python `str` at the boundary. When reading files of unknown encoding:

```python
import chardet

with open(filepath, 'rb') as f:
    raw = f.read()
    detected = chardet.detect(raw)
    encoding = detected['encoding'] or 'utf-8'
    text = raw.decode(encoding, errors='replace')
```

---

---

## 10. Installation & Environment Setup

### Critical: PaddlePaddle GPU is Not on PyPI

PaddlePaddle GPU must be installed from the **official PaddlePaddle package index**, not PyPI. Installing `paddlepaddle-gpu` from PyPI will either fail or install CPU-only.

```bash
# First, check your CUDA version
nvidia-smi  # Look for "CUDA Version: XX.X"

# Install matching PaddlePaddle GPU build
# For CUDA 12.x (recommended):
pip install paddlepaddle-gpu==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/

# For CUDA 11.8:
pip install paddlepaddle-gpu==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/

# Then install PaddleOCR
pip install paddleocr

# If PP-OCRv5 pipeline errors occur:
pip install paddlex[ocr]
```

**Windows CUDA support:** PaddlePaddle GPU supports CUDA up to **12.9** on Windows. CUDA 13.x is NOT supported. If you have a newer driver, install CUDA 12.x runtime alongside it.

**Do NOT use `uv`** to install paddlepaddle-gpu. `uv` has a known bug where it selects the wrong wheel (paddlepaddle vs paddlepaddle-gpu naming mismatch). Use plain `pip`.

### Recommended: Conda Environment

Conda provides the best isolation for PaddlePaddle + PyTorch (from sentence-transformers) coexistence:

```yaml
# environment.yml
name: chinese-ocr
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - numpy
  - pillow
  - conda-forge::opencv  # Use conda opencv to avoid Qt conflicts
  - pip
  - pip:
    # Install paddlepaddle-gpu FIRST via official index
    - paddlepaddle-gpu==3.0.0 --index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/
    - paddleocr
    - paddlex[ocr]         # For PP-OCRv5 pipeline support
    - pyside6
    - mss
    - pynput               # Global hotkeys
    - ebooklib
    - pycorrector[macbert] # CSC with MacBERT backend
    - datasketch            # MinHash LSH
    - sentence-transformers # For BGE-M3 embeddings
    - faiss-cpu             # ANN for large-scale dedup
    - gitpython
    - openai                # OpenRouter-compatible client
    - chardet
    - opencc-python-reimplemented  # Simplified/Traditional conversion
```

**Install order matters:**
1. Create conda env: `conda env create -f environment.yml`
2. Activate: `conda activate chinese-ocr`
3. Verify GPU: `python -c "import paddle; paddle.utils.run_check()"`
4. Verify OCR: `python -c "from paddleocr import PaddleOCR; print('OK')"`

### OpenCV Conflict Note

**Problem:** `pip install opencv-python` installs Qt-based GUI components that conflict with PySide6's Qt installation on Windows. Symptoms: crashes on window creation, missing DLLs.

**Solution:** Use `opencv-python-headless` (no GUI components) OR install opencv via conda-forge (which bundles its own Qt):
```bash
# Option A (preferred with conda)
conda install -c conda-forge opencv

# Option B (pip only)
pip install opencv-python-headless  # Not opencv-python
```

### Python Version Constraint

**Use Python 3.11.** 
- 3.10 and 3.11 are the most tested with PaddlePaddle 3.x on Windows
- Python 3.12+ may have issues with PaddlePaddle and some NLP dependencies
- Python 3.9 works but misses performance improvements in 3.11

### Sentence-Transformers / PyTorch Coexistence

`sentence-transformers` pulls PyTorch. PaddlePaddle and PyTorch can coexist in the same environment — they maintain separate CUDA contexts. However:
- Both consume VRAM when models are loaded
- **Never** hold both a PaddlePaddle (OCR) model and a PyTorch (embedding/CSC) model in VRAM simultaneously on 8 GB VRAM
- Implement explicit `model.unload()` / `del model` + `torch.cuda.empty_cache()` / `paddle.device.cuda.empty_cache()` between stages

### Global Hotkeys (System-Wide F-Keys)

For hotkeys that work when the app window is not focused:
- **`pynput`** — recommended. Cross-platform, no admin required on Windows. Use `pynput.keyboard.Listener`.
- **`keyboard`** — alternative. Requires admin/root on some Windows configs. More features but heavier.
- **Important:** Hotkey listeners must run in a separate thread from the PySide6 event loop. Use `QMetaObject.invokeMethod` or Qt signals to safely trigger GUI updates from the hotkey thread.

---

## 11. Library Quick Reference

### OCR

| Library | Use | Notes |
|---------|-----|-------|
| `paddleocr` | Primary OCR engine | Use PP-OCRv5; install paddlepaddle-gpu from official index |
| `paddlepaddle-gpu` | PaddleOCR GPU backend | Install via official PaddlePaddle index, NOT PyPI |
| `paddlex[ocr]` | PP-OCRv5 pipeline support | Required for PP-OCRv5 features; install if pipeline errors occur |
| `rapidocr-onnxruntime` | ONNX-based PaddleOCR alternative | No PaddlePaddle dep; useful fallback |
| `opencv-python-headless` | Image preprocessing | Use headless to avoid Qt conflict with PySide6 |
| `Pillow` | Image I/O | PIL compatible |
| `mss` | Screen capture | 30x faster than pyautogui; ~45-65ms per region capture |
| `deskew` | Document deskewing | Simpler API than manual OpenCV |

### Chinese NLP

| Library | Use | Notes |
|---------|-----|-------|
| `jieba` | Word segmentation | Fast, good general purpose |
| `pkuseg` | Word segmentation | More accurate, domain models |
| `HanLP` | Full NLP suite | Segmentation, NER, POS, dependency |
| `pycorrector` | Chinese text correction | Wraps KenLM, BERT, MacBERT, T5 |
| `ltp` | Language Technology Platform | HIT's Chinese NLP toolkit |
| `opencc` | Simplified↔Traditional conversion | Conservative, accurate |
| `chardet` | Encoding detection | For legacy documents |

### Deduplication

| Library | Use | Notes |
|---------|-----|-------|
| `datasketch` | MinHash LSH | Near-duplicate detection at scale |
| `simhash` | SimHash fingerprinting | Moderate-scale near-duplicate |
| `semhash` | Semantic dedup with embeddings | Wraps sentence-transformers + ANN |
| `sentence-transformers` | Embedding generation | Load BGE-M3 for Chinese |
| `faiss-cpu` / `faiss-gpu` | ANN similarity search | For large-scale embedding search |

### GUI & Capture

| Library | Use | Notes |
|---------|-----|-------|
| `pyside6` | GUI framework | LGPL license (better than PyQt6 GPL for distribution); same API |
| `mss` | Screen capture | 30x faster than alternatives; use `sct.grab(monitor_dict)` |
| `pynput` | Global hotkeys | Works without admin; run in separate thread from Qt event loop |

### Model Serving (Local)

| Tool | Use | Notes |
|------|-----|-------|
| `ollama` | Local LLM serving | Easiest model management; use with `openai` client at `http://localhost:11434/v1` |
| `llama-cpp-python` | llama.cpp Python bindings | Lower-level, more control |
| `transformers` | HuggingFace model loading | For BERT/MacBERT CSC models |
| `optimum` | Model optimization | Quantization helpers |

### EPUB

| Library | Use | Notes |
|---------|-----|-------|
| `ebooklib` | EPUB2/EPUB3 generation | Control spine order explicitly — do not rely on insertion order |

### Version Control

| Library | Use | Notes |
|---------|-----|-------|
| `gitpython` | Git repo management | Preferred over subprocess calls; cleaner API |

### Utilities

| Library | Use | Notes |
|---------|-----|-------|
| `unicodedata` | Unicode normalization | Built-in Python |
| `regex` | Better regex (Unicode-aware) | Handles CJK ranges better than `re` |
| `kenlm` | N-gram language models | Needs compilation; fast inference |
| `openai` | API client for OpenRouter + Ollama | Use with `base_url` override for both services |
| `opencc-python-reimplemented` | Simplified/Traditional conversion | Pure Python, no system deps |

---

## Appendix: OpenRouter API Setup

OpenRouter uses an OpenAI-compatible API. Use the `openai` library with a custom base URL:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="YOUR_OPENROUTER_API_KEY",
)

response = client.chat.completions.create(
    model="deepseek/deepseek-v3.2",  # or other model ID
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ],
    temperature=0.1,  # Low temperature for correction tasks — less creative, more accurate
    max_tokens=2000,
)
corrected = response.choices[0].message.content
```

**Temperature note:** Use `temperature=0.0–0.2` for OCR correction tasks. Higher temperatures introduce unwanted variation. For dedup judgment (yes/no), use `temperature=0.0`.

---

*Document generated for use with Cline in VS Code. Context7 MCP can resolve specific library APIs on demand. This document covers domain knowledge and pipeline best practices that Context7 does not provide.*
