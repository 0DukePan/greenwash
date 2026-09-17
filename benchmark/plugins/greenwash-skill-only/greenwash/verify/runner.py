"""Running a command safely: a timeout, capped output, redacted secrets.

Every subprocess in the verifier goes through `run`. It stays boring on
purpose: no shell tricks beyond `shell=True` for the command the user
configured. What it does defend against is a suite that runs away -- output
goes to a temp file and only a capped window of it is ever read back, so a
firehose cannot be buffered into memory first; the timeout kills the process
tree, so a grandchild cannot hold the run open past it; and everything
captured passes through redaction before it can reach a report.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
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


def _read_capped(handle, label: str, truncated: list, cap: bool) -> str:
    """Read a capture file, keeping the head and the tail.

    The first error and the final summary both matter, so a capped stream keeps
    both ends with a marker in between -- the same shape reports always had,
    applied to a file instead of to a string that was already in memory.
    """
    end = handle.seek(0, os.SEEK_END)
    if not cap or end <= MAX_STREAM_BYTES:
        handle.seek(0)
        return handle.read().decode("utf-8", "replace")
    truncated.append(f"{label} capped at {MAX_STREAM_BYTES // 1000}kB")
    handle.seek(0)
    head = handle.read(MAX_STREAM_BYTES - TAIL_BYTES).decode("utf-8", "replace")
    handle.seek(end - TAIL_BYTES)
    tail = handle.read(TAIL_BYTES).decode("utf-8", "replace")
    return f"{head}\n... [{label} truncated] ...\n{tail}"


def _spawn(command, cwd, env, stdout, stderr) -> subprocess.Popen:
    """Start the command, its output going to files rather than pipes.

    Pipes are what made the old version's timeout a lie: the cap was applied
    after the whole stream had been read into memory, and a killed shell could
    leave a grandchild holding the pipe open. On POSIX the child also gets its
    own session so the whole group can be stopped at once.
    """
    kwargs: dict = {
        "cwd": cwd, "env": env,
        "stdin": subprocess.DEVNULL, "stdout": stdout, "stderr": stderr,
        "shell": isinstance(command, str),
    }
    if os.name != "nt":
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)


def _kill_tree(proc: subprocess.Popen) -> None:
    """Stop the command and anything it started.

    Killing only the direct child used to leave the test runner alive after
    greenwash returned. The process group on POSIX and `taskkill /T` on
    Windows take the grandchildren with it.
    """
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, check=False)
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:          # pragma: no cover - last resort
        proc.kill()


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
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            proc = _spawn(command, cwd, child_env, out, err)
            try:
                returncode = proc.wait(timeout=timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                returncode = None
                timed_out = True
            stdout = _read_capped(out, "stdout", truncated, cap)
            stderr = _read_capped(err, "stderr", truncated, cap)
    except (OSError, ValueError) as exc:
        return RunResult(command=display, returncode=None,
                         duration_s=round(time.monotonic() - started, 2),
                         error=f"could not run: {exc}")

    stdout, count_out = redact(stdout)
    stderr, count_err = redact(stderr)
    duration = round(time.monotonic() - started, 2)
    if timed_out:
        return RunResult(command=display, returncode=returncode, stdout=stdout,
                         stderr=stderr, duration_s=duration, timed_out=True,
                         error=f"timed out after {timeout}s", truncated=truncated,
                         redactions=count_out + count_err)
    return RunResult(command=display, returncode=returncode, stdout=stdout,
                     stderr=stderr, duration_s=duration, truncated=truncated,
                     redactions=count_out + count_err)
