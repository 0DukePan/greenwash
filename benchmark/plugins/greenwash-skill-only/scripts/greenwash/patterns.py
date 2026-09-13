"""Language packs and shared patterns.

Adding a language = adding its extension to LANGUAGE_BY_EXT and a matching
key in PACKS. Python additionally gets AST-based checks (ast_checks.py); the
other packs are regex-only.
"""

from __future__ import annotations

import os
import re

LITERAL = r"(-?\d+(?:\.\d+)?|'[^']*'|\"[^\"]*\"|True|False|None|nil|null)"

TRIVIAL_LITERALS = {"0", "1", "true", "false", "none", "null", "nil", "''", '""'}

TEST_FILE_RE = re.compile(
    r"(^|/)(tests?|specs?|__tests__)(/|$)"
    r"|(^|/)test_[^/]+\.\w+$"
    r"|[^/]+_test\.\w+$"
    r"|[^/]+\.(?:test|spec)\.\w+$",
    re.IGNORECASE,
)

ASSERT_LITERAL_PATTERNS = [
    rf"assert(?:Equal)?\s*\([^,]+,\s*{LITERAL}\s*\)",
    rf"expect\([^)]*\)\.toBe\(\s*{LITERAL}\s*\)",
    rf"assert\s+.+?\s*==\s*{LITERAL}",
]

# Kept for non-Python hardcoded-return scanning. The optional trailing comment
# matters: an agent that hardcodes and annotates it (`return 5  # matches the
# test`) is the common case, not the exception.
RETURN_LITERAL_PATTERN = rf"return\s+{LITERAL}\s*;?\s*(?:#.*|//.*)?\s*(?:\n|$)"

# Not language-specific; run against every non-Python file.
GENERIC_EXPLOITS = [
    (r"sys\.exit\s*\(\s*0\s*\)",
     "sys.exit(0) -- can force a suite to report success early"),
    (r"os\._exit\s*\(\s*0\s*\)",
     "os._exit(0) -- can force a suite to report success early"),
    (r"process\.exit\s*\(\s*0\s*\)",
     "process.exit(0) -- can force a suite to report success early"),
]

LANGUAGE_BY_EXT = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript", ".ts": "javascript",
    ".tsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".java": "java",
}


PACKS = {
    "python": {
        "skip": [
            (r"@pytest\.mark\.skip", "Python @pytest.mark.skip"),
            (r"@unittest\.skip", "Python @unittest.skip"),
            (r"self\.skipTest\s*\(", "Python self.skipTest("),
            (r"\bpytest\.skip\s*\(", "pytest.skip("),
        ],
        "swallow": [
            (r"except[^:\n]*:\s*pass\b", "Python except ...: pass"),
        ],
        "mock": [
            (r"unittest\.mock\.patch", "unittest.mock.patch"),
            (r"@patch\s*\(", "@patch("),
            (r"\bMagicMock\s*\(", "MagicMock("),
        ],
    },
    "javascript": {
        "skip": [
            (r"\b(?:it|test|describe)\.skip\s*\(", "JS/TS .skip("),
            (r"\bxit\s*\(", "JS/TS xit("),
            (r"\bxdescribe\s*\(", "JS/TS xdescribe("),
            (r"\btest\.todo\s*\(", "JS/TS test.todo("),
            (r"\bit\.only\s*\(", "JS/TS it.only("),
        ],
        "swallow": [
            (r"catch\s*\([^)]*\)\s*\{\s*\}", "empty catch block (JS/TS/Java)"),
            (r"catch\s*\{\s*\}", "empty catch, no binding (JS)"),
        ],
        "mock": [
            (r"jest\.mock\s*\(", "jest.mock("),
            (r"jest\.spyOn\s*\(", "jest.spyOn("),
            (r"sinon\.(?:stub|mock)\s*\(", "sinon.stub/mock("),
        ],
    },
    "go": {
        "skip": [(r"\bt\.Skip\s*\(", "Go t.Skip(")],
        "swallow": [(r"if\s+err\s*!=\s*nil\s*\{\s*\}", "Go: empty `if err != nil {}`")],
        "mock": [],
    },
    "rust": {
        "skip": [(r"#\[ignore\]", "Rust #[ignore]")],
        "swallow": [],
        "mock": [],
    },
    "ruby": {
        "skip": [
            (r"^\s*x(?:it|describe)\b", "RSpec xit/xdescribe"),
            (r"\bpending\s*[\(\"']", "RSpec pending"),
        ],
        "swallow": [],
        "mock": [
            (r"\bdouble\s*\(", "RSpec double("),
            (r"\ballow\s*\(", "RSpec allow("),
        ],
    },
    "java": {
        "skip": [
            (r"@Disabled", "JUnit5 @Disabled"),
            (r"@Ignore", "JUnit4 @Ignore"),
        ],
        "swallow": [(r"catch\s*\([^)]*\)\s*\{\s*\}", "empty catch block")],
        "mock": [(r"Mockito\.", "Mockito."), (r"@Mock\b", "@Mock")],
    },
}


def language_of(filename: str):
    return LANGUAGE_BY_EXT.get(os.path.splitext(filename)[1].lower())


def is_test_file(filename: str) -> bool:
    return bool(TEST_FILE_RE.search(filename))
