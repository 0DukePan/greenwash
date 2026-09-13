"""Secret redaction for captured test output.

Test output is captured and stored in reports, which means it can leak a
credential that a test printed. Everything that leaves `runner.run` passes
through here first, and the number of substitutions is reported so a reader
knows redaction happened.
"""

from __future__ import annotations

import re

REPLACEMENT = "<redacted>"

PATTERNS = [
    # key = value / key: value, the shape env dumps and config echoes take
    (re.compile(r"""(?ix)
        \b(api[_-]?key|secret|token|password|passwd|authorization|bearer|
           access[_-]?key|private[_-]?key)\b
        \s*[:=]\s*
        ["']?([A-Za-z0-9_\-./+]{8,})["']?"""), r"\1=" + REPLACEMENT),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), REPLACEMENT),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}"), REPLACEMENT),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), REPLACEMENT),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), REPLACEMENT),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"), REPLACEMENT),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REPLACEMENT),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
     REPLACEMENT),
    (re.compile(r"(?i)\b(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1" + REPLACEMENT + "@"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.S), REPLACEMENT),
]


def redact(text: str) -> tuple:
    """(clean_text, substitutions). Never raises, never returns None."""
    if not text:
        return "", 0
    count = 0
    for pattern, replacement in PATTERNS:
        text, hits = pattern.subn(replacement, text)
        count += hits
    return text, count
