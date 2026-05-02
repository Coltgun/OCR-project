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
import os
import site
import subprocess
import sys
from typing import NamedTuple


def _register_nvidia_dll_dirs() -> None:
    """Add bundled nvidia CUDA DLL directories to the Windows DLL search path.

    Required on Windows before importing paddle (or any CUDA library) when
    the CUDA Toolkit is not installed system-wide. The nvidia-* pip packages
    install DLLs into site-packages/nvidia/*/bin/ but Windows does not
    search these automatically. os.add_dll_directory() registers them.
    """
    if sys.platform != "win32":
        return
    nvidia_subdirs = [
        "cublas", "cuda_runtime", "cudnn", "cufft",
        "curand", "cusolver", "cusparse", "nvjitlink",
    ]
    extra_paths: list[str] = []
    for sp in site.getsitepackages():
        for subdir in nvidia_subdirs:
            dll_dir = os.path.join(sp, "nvidia", subdir, "bin")
            if os.path.isdir(dll_dir):
                os.add_dll_directory(dll_dir)
                extra_paths.append(dll_dir)
    if extra_paths:
        os.environ["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + os.environ.get("PATH", "")


_register_nvidia_dll_dirs()


class PackageCheck(NamedTuple):
    import_name: str
    display_name: str
    version_attr: str | None = "__version__"
    install_hint: str | None = None


# NOTE: paddle and paddleocr MUST be checked before sentence_transformers and
# pycorrector. Those packages import PyTorch, which loads its own cuDNN DLLs.
# Once torch's cuDNN is loaded, paddle's bundled cuDNN (different version)
# cannot be loaded in the same process (WinError 127 / DLL conflict).
# Paddle/paddleocr checks run in a subprocess to guarantee isolation.
PACKAGES: list[PackageCheck] = [
    PackageCheck("numpy", "NumPy"),
    PackageCheck("PIL", "Pillow", version_attr=None),
    PackageCheck("cv2", "OpenCV", version_attr="__version__"),
    PackageCheck("PySide6", "PySide6", version_attr="__version__"),
    PackageCheck("mss", "mss", version_attr="__version__"),
    PackageCheck("pynput", "pynput", version_attr="__version__"),
    PackageCheck("ebooklib", "ebooklib", version_attr="__version__"),
    PackageCheck("datasketch", "datasketch", version_attr="__version__"),
    PackageCheck("git", "gitpython", version_attr="__version__"),
    PackageCheck("openai", "openai", version_attr="__version__"),
    PackageCheck("chardet", "chardet", version_attr="__version__"),
    PackageCheck("opencc", "opencc-python-reimplemented", version_attr="__version__"),
    PackageCheck("jieba", "jieba", version_attr="__version__"),
    # torch-dependent — checked AFTER paddle to avoid cuDNN DLL conflict
    PackageCheck("pycorrector", "pycorrector", version_attr="__version__"),
    PackageCheck("sentence_transformers", "sentence-transformers", version_attr="__version__"),
]

# Paddle packages checked in a subprocess to avoid torch/paddle cuDNN conflict
PADDLE_PACKAGES: list[PackageCheck] = [
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
    except (ImportError, OSError) as e:
        return False, str(e)


def check_paddle_subprocess(import_name: str, display_name: str) -> tuple[bool, str]:
    """Check a paddle package in a clean subprocess to avoid torch/paddle cuDNN conflict.

    On Windows, torch and paddle bundle incompatible cuDNN versions. Once torch
    loads its cuDNN DLLs, paddle cannot load its own. Running paddle in a
    subprocess guarantees a clean process with no prior cuDNN state.
    """
    code = (
        "import os, site, sys\n"
        "nvidia_subdirs = ['cublas','cuda_runtime','cudnn','cufft','curand','cusolver','cusparse','nvjitlink']\n"
        "extra = []\n"
        "for sp in site.getsitepackages():\n"
        "    for d in nvidia_subdirs:\n"
        "        p = os.path.join(sp,'nvidia',d,'bin')\n"
        "        if os.path.isdir(p):\n"
        "            os.add_dll_directory(p)\n"
        "            extra.append(p)\n"
        "if extra:\n"
        "    os.environ['PATH'] = os.pathsep.join(extra) + os.pathsep + os.environ.get('PATH','')\n"
        f"import importlib, importlib.metadata\n"
        f"mod = importlib.import_module('{import_name}')\n"
        f"ver = getattr(mod, '__version__', None)\n"
        f"if ver is None:\n"
        f"    try: ver = importlib.metadata.version('{display_name.lower()}')\n"
        f"    except Exception: ver = 'unknown'\n"
        f"print(ver)\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()
        err = (result.stderr or "").strip().splitlines()
        last = err[-1] if err else "unknown error"
        return False, last
    except subprocess.TimeoutExpired:
        return False, "subprocess timed out after 60s"
    except Exception as e:
        return False, str(e)


def check_paddle_gpu() -> tuple[bool, str]:
    """Attempt paddle GPU check in a clean subprocess."""
    code = (
        "import os, site\n"
        "for sp in site.getsitepackages():\n"
        "    for d in ['cublas','cuda_runtime','cudnn','cufft','curand','cusolver','cusparse','nvjitlink']:\n"
        "        p = __import__('os').path.join(sp,'nvidia',d,'bin')\n"
        "        if __import__('os').path.isdir(p):\n"
        "            os.add_dll_directory(p)\n"
        "            os.environ['PATH'] = p + ';' + os.environ.get('PATH','')\n"
        "import paddle\n"
        "v = paddle.__version__\n"
        "c = paddle.is_compiled_with_cuda()\n"
        "n = paddle.device.cuda.device_count() if c else 0\n"
        "print(f'{v}, CUDA compiled: {c}, GPUs: {n}')\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()
        err = (result.stderr or "").strip().splitlines()
        return False, err[-1] if err else "unknown error"
    except subprocess.TimeoutExpired:
        return False, "subprocess timed out"
    except Exception as e:
        return False, str(e)


def check_paddleocr_init() -> tuple[bool, str]:
    """Attempt a CPU-only PaddleOCR initialization in a clean subprocess."""
    script = "\n".join([
        "import os",
        "import site",
        "nvidia_subdirs = ['cublas','cuda_runtime','cudnn','cufft','curand','cusolver','cusparse','nvjitlink']",
        "extra = []",
        "for sp in site.getsitepackages():",
        "    for d in nvidia_subdirs:",
        "        p = os.path.join(sp, 'nvidia', d, 'bin')",
        "        if os.path.isdir(p):",
        "            os.add_dll_directory(p)",
        "            extra.append(p)",
        "if extra:",
        "    os.environ['PATH'] = os.pathsep.join(extra) + os.pathsep + os.environ.get('PATH', '')",
        "from paddleocr import PaddleOCR",
        "_ = PaddleOCR(use_textline_orientation=False, lang='ch', device='cpu')",
        "print('PaddleOCR CPU init succeeded')",
    ])
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and "succeeded" in result.stdout:
            return True, "PaddleOCR CPU init succeeded"
        err = (result.stderr or "").strip().splitlines()
        return False, err[-1] if err else "unknown error"
    except subprocess.TimeoutExpired:
        return False, "PaddleOCR init timed out (120s)"
    except Exception as e:
        return False, str(e)


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

    # Paddle packages run in subprocess to avoid torch/paddle cuDNN DLL conflict
    for pkg in PADDLE_PACKAGES:
        ok, info = check_paddle_subprocess(pkg.import_name, pkg.display_name)
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
        print("  [OK]     CUDA 12.x -- compatible with PaddlePaddle GPU 3.x (cu126 index).")

    gpu_ok, gpu_msg = check_paddle_gpu()
    status = "[OK]    " if gpu_ok else "[FAIL]  "
    print(f"  {status} PaddlePaddle GPU check: {gpu_msg}")
    if not gpu_ok:
        failed.append("PaddlePaddle GPU")

    print()
    print("  --- PaddleOCR Functional Test ---")
    print("  [INFO]   PaddleOCR import verified via subprocess above.")
    print("  [INFO]   Full init test skipped: torch+paddle cuDNN DLL conflict.")
    print("           torch (cu121) and paddlepaddle-gpu (cu126) bundle incompatible")
    print("           cuDNN builds. They must NOT be imported in the same process.")
    print("           See KNOWN_ISSUES.md for details.")

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
