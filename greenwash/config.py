"""`.greenwash/config.json`: optional, and entirely an override.

Zero-config is the default. This file exists so that a team can pin a test
command, point at a held-out suite, or opt into enforcement -- never because
the tool needed to be configured to work at all.

Loading is forgiving by design: a corrupt or half-written config falls back to
the defaults and records why, because a broken config file must not be able to
stop a report from being produced.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = ".greenwash"
CONFIG_FILE = "config.json"
REPORT_MODE = "report"
ENFORCE_MODE = "enforce"

DEFAULTS = {
    "mode": REPORT_MODE,
    "auto_verify": False,
    "test_command": None,
    "heldout": None,
    "timeout": 120,
    "block_on": ["NOT_VERIFIED", "VERIFICATION_FAILED"],
    "ignore_rules": [],
    "agent": "",
}

ENV_OVERRIDES = {
    "GREENWASH_AUTO": ("auto_verify", lambda value: value == "1"),
    "GREENWASH_TEST_CMD": ("test_command", str),
    "GREENWASH_HELDOUT": ("heldout", str),
    "GREENWASH_MODE": ("mode", str),
    "GREENWASH_TIMEOUT": ("timeout", int),
}


@dataclass
class Config:
    values: dict = field(default_factory=lambda: dict(DEFAULTS))
    path: str = ""
    source: str = "defaults"
    problems: list = field(default_factory=list)

    def __getitem__(self, key):
        return self.values.get(key, DEFAULTS.get(key))

    def get(self, key, default=None):
        return self.values.get(key, DEFAULTS.get(key, default))

    @property
    def mode(self) -> str:
        return ENFORCE_MODE if self.get("mode") == ENFORCE_MODE else REPORT_MODE

    @property
    def enforcing(self) -> bool:
        return self.mode == ENFORCE_MODE


def config_path(root=".") -> Path:
    return Path(root) / CONFIG_DIR / CONFIG_FILE


def load(root=".", env=None) -> Config:
    env = os.environ if env is None else env
    config = Config()
    path = config_path(root)

    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                config.values.update({k: v for k, v in data.items() if k in DEFAULTS})
                config.source = str(path)
            else:
                config.problems.append(f"{path} is not a JSON object; ignoring it")
        except (OSError, json.JSONDecodeError) as exc:
            config.problems.append(f"could not read {path} ({exc}); using defaults")
    config.path = str(path)

    for name, (key, convert) in ENV_OVERRIDES.items():
        raw = env.get(name)
        if raw in (None, ""):
            continue
        try:
            config.values[key] = convert(raw)
        except (TypeError, ValueError):
            config.problems.append(f"ignoring invalid {name}={raw!r}")
        else:
            config.source = f"{config.source} + {name}"

    return config


def save(values: dict, root=".") -> str:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULTS, **{k: v for k, v in values.items() if k in DEFAULTS}}
    path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return str(path)


def initialized(root=".") -> bool:
    return config_path(root).is_file()
