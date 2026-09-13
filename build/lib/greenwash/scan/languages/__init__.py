"""Language support.

`packs.py` holds the regex tables and language detection; `python_ast.py` is
the only structural implementation, because Python is the only language in the
set that ships a parser we can rely on everywhere.
"""

from __future__ import annotations

from .packs import (LANGUAGE_BY_EXT, PACKS, is_test_file, language_of,
                    literals_from_text)
from .python_ast import PythonModule

__all__ = ["LANGUAGE_BY_EXT", "PACKS", "is_test_file", "language_of",
           "literals_from_text", "PythonModule"]
