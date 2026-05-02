"""
cuda_utils -- Windows CUDA DLL directory registration.

On Windows, pip-installed nvidia-* packages place CUDA DLLs in
site-packages/nvidia/*/bin/ which is not on the DLL search PATH.
Call register_nvidia_dll_dirs() before any import of paddle, torch,
or other CUDA-dependent libraries to prevent WinError 127.

Usage:
    from utils.cuda_utils import register_nvidia_dll_dirs
    register_nvidia_dll_dirs()
    import paddle  # now safe
"""

from __future__ import annotations

import logging
import os
import site
import sys

logger = logging.getLogger(__name__)

_NVIDIA_SUBDIRS: tuple[str, ...] = (
    "cublas",
    "cuda_runtime",
    "cudnn",
    "cufft",
    "curand",
    "cusolver",
    "cusparse",
    "nvjitlink",
)


def register_nvidia_dll_dirs() -> int:
    """Register all bundled nvidia CUDA DLL directories on Windows.

    No-op on non-Windows platforms.

    Returns:
        Number of directories successfully registered.
    """
    if sys.platform != "win32":
        return 0

    registered = 0
    extra_paths: list[str] = []

    for sp in site.getsitepackages():
        for subdir in _NVIDIA_SUBDIRS:
            dll_dir = os.path.join(sp, "nvidia", subdir, "bin")
            if os.path.isdir(dll_dir):
                try:
                    os.add_dll_directory(dll_dir)
                    extra_paths.append(dll_dir)
                    logger.debug("cuda_utils: registered DLL dir '%s'", dll_dir)
                    registered += 1
                except OSError as exc:
                    logger.warning("cuda_utils: failed to register '%s': %s", dll_dir, exc)

    if extra_paths:
        os.environ["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + os.environ.get("PATH", "")

    logger.debug("cuda_utils: registered %d nvidia DLL directories.", registered)
    return registered
