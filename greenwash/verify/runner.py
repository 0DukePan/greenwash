"""Running a command safely: a timeout, capped output, redacted secrets.

Every subprocess in the verifier goes through `run`. It is deliberately
boring: no streaming, no shell tricks beyond `shell=True` for the command the
user configured, and a hard cap on how much text can end up in a report.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field

from .redact import redact

DEFAULT_TIMEOUT = 120
MAX_STREAM_BYTES = 1_000_000
TAIL_BYTES = 4_000


@dataclass
class RunResult:
    command: str = ""
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    timed_out: bool = False
    error: str = ""
    truncated: list = field(default_factory=list)
    redactions: int = 0

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.error

    def tail(self, limit: int = 2_000) -> str:
        text = (self.stdout or "") + "\n" + (self.stderr or "")
        return text.strip()[-limit:]


def _cap(text: str, label: str, truncated: list) -> str:
    """Keep the head and the tail: the first error and the final summary both matter."""
    encoded = text.encode("utf-8", "replace")
    if len(encoded) <= MAX_STREAM_BYTES:
        return text
    head = encoded[:MAX_STREAM_BYTES - TAIL_BYTES].decode("utf-8", "replace")
    tail = encoded[-TAIL_BYTES:].decode("utf-8", "replace")
    truncated.append(f"{label} capped at {MAX_STREAM_BYTES // 1000}kB")
    return f"{head}\n... [{label} truncated] ...\n{tail}"


def run(command, cwd=None, timeout: int = DEFAULT_TIMEOUT, env=None,
        cap: bool = True) -> RunResult:
    """Run a command, capturing redacted output. `command` may be a str or argv.

    The child is asked for UTF-8 and decoded as UTF-8, on every platform. Left
    to the locale, a Python child on a UTF-8 console hands back bytes this
    process then reads as cp1252 -- and the captured test output, which ends up
    in reports, arrives as mojibake.
    """
    started = time.monotonic()
    truncated: list = []
    display = command if isinstance(command, str) else " ".join(command)
    child_env = {**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})}

    try:
        proc = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, shell=isinstance(command, str),
            timeout=timeout, env=child_env, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as exc:
        stdout = _decode(exc.stdout)
        stderr = _decode(exc.stderr)
        stdout, count_out = redact(_cap(stdout, "stdout", truncated) if cap else stdout)
        stderr, count_err = redact(_cap(stderr, "stderr", truncated) if cap else stderr)
        return RunResult(command=display, returncode=None, stdout=stdout, stderr=stderr,
                         duration_s=round(time.monotonic() - started, 2), timed_out=True,
                         error=f"timed out after {timeout}s", truncated=truncated,
                         redactions=count_out + count_err)
    except (OSError, ValueError) as exc:
        return RunResult(command=display, returncode=None,
                         duration_s=round(time.monotonic() - started, 2),
                         error=f"could not run: {exc}")

    stdout, count_out = redact(_cap(proc.stdout or "", "stdout", truncated) if cap else proc.stdout or "")
    stderr, count_err = redact(_cap(proc.stderr or "", "stderr", truncated) if cap else proc.stderr or "")
    return RunResult(command=display, returncode=proc.returncode, stdout=stdout, stderr=stderr,
                     duration_s=round(time.monotonic() - started, 2), truncated=truncated,
                     redactions=count_out + count_err)


def _decode(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)
