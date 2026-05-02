"""
verify_env.py — Environment verification script for the Simplified Chinese OCR app.

Checks all required package imports, versions, and GPU/CUDA availability.
Prints [OK] or [MISSING] for each package, then a summary with install
instructions for any missing packages.

Usage:
    conda activate chinese-ocr
    python scripts/verify_env.py
"""

from __future__ import annotations

import importlib
import importlib.metadata
import subprocess
import sys
from typing import NamedTuple


class PackageCheck(NamedTuple):
    import_name: str
    display_name: str
    version_attr: str | None = "__version__"
    install_hint: str | None = None


PACKAGES: list[PackageCheck] = [
    PackageCheck("numpy", "NumPy"),
    PackageCheck("PIL", "Pillow", version_attr=None),
    PackageCheck("cv2", "OpenCV", version_attr="__version__"),
    PackageCheck("PySide6", "PySide6", version_attr="__version__"),
    PackageCheck("mss", "mss", version_attr="__version__"),
    PackageCheck("pynput", "pynput", version_attr="__version__"),
    PackageCheck("ebooklib", "ebooklib", version_attr="__version__"),
    PackageCheck("pycorrector", "pycorrector", version_attr="__version__"),
    PackageCheck("datasketch", "datasketch", version_attr="__version__"),
    PackageCheck("sentence_transformers", "sentence-transformers", version_attr="__version__"),
    PackageCheck("git", "gitpython", version_attr="__version__"),
    PackageCheck("openai", "openai", version_attr="__version__"),
    PackageCheck("chardet", "chardet", version_attr="__version__"),
    PackageCheck("opencc", "opencc-python-reimplemented", version_attr="__version__"),
    PackageCheck("jieba", "jieba", version_attr="__version__"),
    PackageCheck("paddle", "PaddlePaddle", version_attr="__version__"),
    PackageCheck("paddleocr", "PaddleOCR", version_attr="__version__"),
]

INSTALL_INSTRUCTIONS = """
================================================================================
ENVIRONMENT SETUP — Install missing packages in this exact order:
================================================================================

Step 1: Create and activate the conda environment
    conda create -n chinese-ocr python=3.11 -y
    conda activate chinese-ocr

Step 2: Install NumPy, Pillow, OpenCV via conda-forge
    conda install -c conda-forge numpy pillow -y
    conda install -c conda-forge opencv -y

Step 3: Install PySide6
    pip install PySide6

Step 4: Install PaddlePaddle GPU (official index -- NOT PyPI)
    pip install paddlepaddle-gpu==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/

    WARNING: Do NOT use uv for this step. Use plain pip only.
    NOTE: Requires CUDA 12.x. Your driver shows CUDA 13.1 -- see KNOWN_ISSUES.md.
          Install CUDA 12.6 Toolkit first: https://developer.nvidia.com/cuda-12-6-0-download-archive

Step 5: Install PaddleOCR
    pip install paddleocr
    pip install paddlex[ocr]

Step 6: Install PyTorch (for MacBERT, BGE-M3, sentence-transformers)
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

Step 7: Install remaining dependencies
    pip install mss ebooklib pycorrector datasketch sentence-transformers gitpython openai pynput chardet opencc-python-reimplemented jieba

================================================================================
"""


def check_package(pkg: PackageCheck) -> tuple[bool, str]:
    """Attempt to import a package and retrieve its version. Returns (ok, version_str)."""
    try:
        mod = importlib.import_module(pkg.import_name)
        if pkg.version_attr is not None:
            version = getattr(mod, pkg.version_attr, "unknown")
        else:
            try:
                version = importlib.metadata.version(pkg.display_name.lower().replace("-", "_"))
            except Exception:
                try:
                    version = importlib.metadata.version(pkg.display_name.lower())
                except Exception:
                    version = "unknown"
        return True, str(version)
    except ImportError as e:
        return False, str(e)


def check_paddle_gpu() -> tuple[bool, str]:
    """Attempt paddle GPU check. Returns (ok, message)."""
    try:
        import paddle  # noqa: PLC0415
        is_compiled = paddle.is_compiled_with_cuda()
        if not is_compiled:
            return False, "paddle is NOT compiled with CUDA (CPU-only build)"
        paddle_version = paddle.__version__
        try:
            device_count = paddle.device.cuda.device_count()
            return True, f"paddle {paddle_version}, CUDA compiled, {device_count} GPU(s) found"
        except Exception as e:
            return False, f"paddle {paddle_version}, CUDA compiled but GPU query failed: {e}"
    except ImportError:
        return False, "paddle not importable — PaddlePaddle not installed"
    except Exception as e:
        return False, f"paddle GPU check error: {e}"


def check_paddleocr_init() -> tuple[bool, str]:
    """Attempt a CPU-only PaddleOCR initialization to confirm the install is functional."""
    try:
        from paddleocr import PaddleOCR  # noqa: PLC0415
        _ = PaddleOCR(use_textline_orientation=False, lang="ch", device="cpu")
        return True, "PaddleOCR CPU init succeeded"
    except ImportError:
        return False, "paddleocr not importable — not installed"
    except Exception as e:
        return False, f"PaddleOCR init failed: {e}"


def check_cuda_version() -> str:
    """Run nvidia-smi and return the CUDA version string."""
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            if "CUDA Version" in line:
                parts = line.split("CUDA Version:")
                if len(parts) > 1:
                    return parts[1].strip().split()[0]
        return "nvidia-smi ran but CUDA version not found in output"
    except FileNotFoundError:
        return "nvidia-smi not found — NVIDIA driver may not be installed"
    except subprocess.TimeoutExpired:
        return "nvidia-smi timed out"
    except Exception as e:
        return f"nvidia-smi error: {e}"


def check_python_version() -> tuple[bool, str]:
    """Verify Python is 3.11.x."""
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    ok = v.major == 3 and v.minor == 11
    return ok, version_str


def main() -> None:
    print("=" * 72)
    print("  Simplified Chinese OCR App -- Environment Verification")
    print("=" * 72)
    print()

    failed: list[str] = []

    # Python version
    py_ok, py_ver = check_python_version()
    status = "[OK]    " if py_ok else "[WARN]  "
    note = "" if py_ok else " (expected 3.11.x -- other versions may have PaddlePaddle issues)"
    print(f"  {status} Python {py_ver}{note}")
    if not py_ok:
        failed.append("Python 3.11 required")

    print()
    print("  --- Package Imports ---")

    for pkg in PACKAGES:
        ok, info = check_package(pkg)
        if ok:
            print(f"  [OK]     {pkg.display_name:<30} {info}")
        else:
            print(f"  [MISSING] {pkg.display_name:<29} {info}")
            failed.append(pkg.display_name)

    print()
    print("  --- GPU / CUDA ---")

    cuda_ver = check_cuda_version()
    print(f"  [INFO]   nvidia-smi CUDA Version:         {cuda_ver}")
    if cuda_ver.startswith("13."):
        print("  [WARN]   CUDA 13.x detected -- PaddlePaddle GPU requires CUDA <=12.9.")
        print("           See KNOWN_ISSUES.md for resolution steps.")
    elif cuda_ver.startswith("12."):
        print("  [OK]     CUDA 12.x -- compatible with PaddlePaddle GPU 3.0.0 (cu126 index).")

    gpu_ok, gpu_msg = check_paddle_gpu()
    status = "[OK]    " if gpu_ok else "[FAIL]  "
    print(f"  {status} PaddlePaddle GPU check: {gpu_msg}")
    if not gpu_ok:
        failed.append("PaddlePaddle GPU")

    print()
    print("  --- PaddleOCR Functional Test (CPU mode) ---")
    ocr_ok, ocr_msg = check_paddleocr_init()
    status = "[OK]    " if ocr_ok else "[FAIL]  "
    print(f"  {status} {ocr_msg}")
    if not ocr_ok:
        failed.append("PaddleOCR functional init")

    print()
    print("=" * 72)
    if not failed:
        print("  ALL CHECKS PASSED — environment is ready.")
    else:
        print(f"  {len(failed)} check(s) failed:")
        for item in failed:
            print(f"    - {item}")
        print(INSTALL_INSTRUCTIONS)
    print("=" * 72)


if __name__ == "__main__":
    main()
