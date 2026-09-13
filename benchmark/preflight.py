#!/usr/bin/env python3
"""Fail fast if headless Claude Code cannot reach a model.

The benchmark is worthless if every run dies at the API. This makes one
trivial call and reports the actual reason (missing key, wrong base URL,
HTTP 402 out of credits, unknown model) in seconds instead of after a long
run of failures.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys


def main() -> None:
    claude = shutil.which("claude") or "claude"
    model = os.environ.get("GREENWASH_BENCH_MODEL")
    cmd = [claude, "-p", "Reply with exactly: OK", "--output-format", "json"]
    if model:
        cmd += ["--model", model]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        sys.exit("preflight: `claude` not found on PATH")
    except subprocess.TimeoutExpired:
        sys.exit("preflight: `claude -p` timed out")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit("preflight: could not parse claude output:\n"
                 f"  stdout: {result.stdout[:300]}\n  stderr: {result.stderr[:300]}")

    if data.get("is_error"):
        sys.exit(
            "preflight: model not reachable.\n"
            f"  {str(data.get('result', ''))[:300]}\n"
            "  Fix ANTHROPIC_BASE_URL (must be https and funded) and/or set\n"
            "  --model / GREENWASH_BENCH_MODEL to a model the account can use."
        )

    print(f"preflight: OK (model={data.get('model') or model or 'default'}, "
          f"cost=${data.get('total_cost_usd', 0)})")


if __name__ == "__main__":
    main()
