"""
ocr/stages/_torch_service.py — generic long-lived torch subprocess service.

Provides TorchSubprocessService: a reusable helper that keeps a child Python
process alive across multiple calls.  The child reads JSON-line requests from
stdin and writes JSON-line responses to stdout.

Reused by BertCorrectionStage and EmbeddingDeduplicationStage.

Protocol:
    Parent → child (first line):  config/init JSON
    Child  → parent (first line): {"ready": true}
    Per call:
        Parent → child: {"request": <payload>}
        Child  → parent: {"ok": true,  "result": <data>}
                      or {"ok": false, "error": "message"}
    Shutdown:
        Parent → child: {"shutdown": true}
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


def _build_clean_env() -> dict[str, str]:
    """Return a minimal env dict that isolates torch DLLs from paddle."""
    env = {
        k: v for k, v in os.environ.items()
        if k.upper() in (
            "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
            "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
            "PYTHONPATH", "PYTHONHOME",
            "CONDA_PREFIX", "CONDA_DEFAULT_ENV",
        )
    }
    env["PATH"] = os.path.join(os.environ.get("SYSTEMROOT", "C:\\Windows"), "System32")
    return env


class TorchSubprocessService:
    """Keep a torch-based child process alive for repeated inference calls.

    Args:
        script_path: Absolute path to the child script (e.g. _bert_subprocess.py).
        init_payload: Serialisable dict sent as the first stdin line (config).
        idle_timeout_s: Not yet implemented (placeholder for future idle shutdown).
    """

    def __init__(
        self,
        script_path: Path,
        init_payload: dict,
        idle_timeout_s: float = 600.0,
    ) -> None:
        self._script_path = script_path
        self._init_payload = init_payload
        self._idle_timeout_s = idle_timeout_s
        self._proc: subprocess.Popen | None = None  # type: ignore[type-arg]
        self._stderr_lines: list[str] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(self, request_payload: object) -> object:
        """Send *request_payload* to the child and return its result.

        Lazily starts the child on first call.  Raises RuntimeError on any
        protocol or process error; caller is responsible for fallback.

        Args:
            request_payload: Any JSON-serialisable object.

        Returns:
            The "result" field from the child's response.
        """
        with self._lock:
            self._ensure_started()
            assert self._proc is not None

            req_line = json.dumps({"request": request_payload}) + "\n"
            try:
                self._proc.stdin.write(req_line)  # type: ignore[union-attr]
                self._proc.stdin.flush()  # type: ignore[union-attr]
            except OSError as exc:
                self._proc = None
                raise RuntimeError(f"TorchSubprocessService: write failed: {exc}") from exc

            resp_line = self._proc.stdout.readline()  # type: ignore[union-attr]
            if not resp_line:
                exit_code = self._proc.poll()
                self._log_stderr()
                self._proc = None
                raise RuntimeError(
                    f"TorchSubprocessService: child EOF (exit={exit_code})"
                )

            try:
                resp = json.loads(resp_line)
            except json.JSONDecodeError as exc:
                self._proc = None
                raise RuntimeError(
                    f"TorchSubprocessService: response not JSON: {resp_line!r}"
                ) from exc

            if not resp.get("ok"):
                raise RuntimeError(
                    f"TorchSubprocessService: child error: {resp.get('error', 'unknown')}"
                )

            return resp["result"]

    def shutdown(self) -> None:
        """Send shutdown signal and wait for the child to exit."""
        with self._lock:
            if self._proc is None:
                return
            try:
                self._proc.stdin.write(json.dumps({"shutdown": True}) + "\n")  # type: ignore[union-attr]
                self._proc.stdin.flush()  # type: ignore[union-attr]
                self._proc.stdin.close()  # type: ignore[union-attr]
            except OSError:
                pass
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            self._proc = None

    @property
    def is_running(self) -> bool:
        """True if the child process is currently alive."""
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_started(self) -> None:
        """Start the child if not already running (called under self._lock)."""
        if self._proc is not None and self._proc.poll() is None:
            return

        self._stderr_lines = []
        self._proc = subprocess.Popen(
            [sys.executable, str(self._script_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=_build_clean_env(),
            bufsize=1,
        )

        stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        stderr_thread.start()

        # Send init payload
        init_line = json.dumps(self._init_payload) + "\n"
        self._proc.stdin.write(init_line)  # type: ignore[union-attr]
        self._proc.stdin.flush()  # type: ignore[union-attr]

        # Wait for ready
        ready_line = self._proc.stdout.readline()  # type: ignore[union-attr]
        if not ready_line:
            self._log_stderr()
            raise RuntimeError("TorchSubprocessService: child did not send ready signal.")
        try:
            ready = json.loads(ready_line)
            if not ready.get("ready"):
                raise RuntimeError(
                    f"TorchSubprocessService: unexpected ready line: {ready_line!r}"
                )
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"TorchSubprocessService: ready line not JSON: {ready_line!r}"
            ) from exc

        logger.debug("TorchSubprocessService: child started (pid=%d).", self._proc.pid)

    def _drain_stderr(self) -> None:
        for line in self._proc.stderr:  # type: ignore[union-attr]
            self._stderr_lines.append(line.rstrip())

    def _log_stderr(self) -> None:
        if self._stderr_lines:
            logger.error(
                "TorchSubprocessService stderr:\n%s",
                "\n".join(self._stderr_lines[-30:]),
            )
