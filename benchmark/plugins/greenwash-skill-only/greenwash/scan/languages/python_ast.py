"""Structural checks for Python, parsed once per file.

Regex cannot follow a value one hop away (`result = 5` then `return result`)
and breaks on a trailing comment (`return 5  # fixed`). Parsing and flagging
only the nodes that land on *added* diff lines fixes both, and cuts false
positives because it reasons about structure instead of text.

`PythonModule` parses once and answers every query, which matters: the
500-file budget in the tests would not survive five parses per file.
"""

from __future__ import annotations

import ast
from typing import Iterable, Optional


def textual_forms(value) -> set:
    """The literal spellings a test assertion could use for this value."""
    if isinstance(value, bool):
        return {str(value)}
    if value is None:
        return {"None", "null", "nil"}
    if isinstance(value, str):
        return {f"'{value}'", f'"{value}"'}
    if isinstance(value, (int, float)):
        return {repr(value), str(value)}
    return set()


SKIP_DECORATORS = ("pytest.mark.skip", "unittest.skip")
SKIP_CALLS = ("pytest.skip", "self.skipTest", "unittest.skip")


class PythonModule:
    """A parsed Python file. Returns raw findings; rules turn them into Signals."""

    def __init__(self, path: str):
        self.path = path
        try:
            # utf-8-sig, not utf-8: a byte-order mark is legal Python source and
            # common on Windows (PowerShell, Visual Studio and Notepad all write
            # one), and `ast.parse` rejects a U+FEFF left at the start of the
            # string. Read as plain utf-8, every AST rule went silent on such a
            # file -- no signal, no note, and a report that read as clean.
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as handle:
                self.tree: Optional[ast.AST] = ast.parse(handle.read())
        except (OSError, SyntaxError, ValueError):
            self.tree = None

    @property
    def ok(self) -> bool:
        return self.tree is not None

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _spans(node) -> range:
        low = getattr(node, "lineno", None)
        if low is None:
            return range(0)
        high = getattr(node, "end_lineno", low) or low
        return range(low, high + 1)

    def _touches(self, node, added_lines: Iterable[int]) -> bool:
        added = set(added_lines)
        return any(line in added for line in self._spans(node))

    @staticmethod
    def _is_noop(stmt) -> bool:
        if isinstance(stmt, ast.Pass):
            return True
        return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)

    # -- queries ---------------------------------------------------------------

    def skip_sites(self, added_lines) -> list:
        """Disabled tests, by structure, with the justified ones marked.

        A file that merely *mentions* `@pytest.mark.skip` -- a pattern table, a
        docstring, this repo's own scanner -- is not skipping anything. A skip
        that carries an explicit reason or a condition (`skipif`) is a
        legitimate, justified skip; the caller reports it for review rather
        than accusing it. A bare skip is suppression.
        """
        found = []
        if not self.ok:
            return found

        def justified(node) -> bool:
            if not isinstance(node, ast.Call):
                return False
            if "skipif" in ast.unparse(node.func):
                return True
            for keyword in node.keywords or []:
                if keyword.arg == "reason" and isinstance(keyword.value, ast.Constant):
                    return bool(str(keyword.value.value).strip())
            return False

        for node in ast.walk(self.tree):
            for decorator in getattr(node, "decorator_list", []) or []:
                text = ast.unparse(decorator)
                if text.startswith(SKIP_DECORATORS) and self._touches(decorator, added_lines):
                    found.append((getattr(decorator, "lineno", None),
                                  f"{text} on {getattr(node, 'name', '?')}",
                                  justified(decorator)))
            if isinstance(node, ast.Call) and self._touches(node, added_lines):
                text = ast.unparse(node.func)
                if text in SKIP_CALLS:
                    found.append((getattr(node, "lineno", None), f"{text}(...) called",
                                  justified(node)))
        return found

    def hardcoded_returns(self, added_lines, asserted_literals) -> list:
        """Return statements whose value a test asserts against.

        Catches the one-hop indirection (`value = 5` ... `return value`) when
        the assignment itself is on an added line.
        """
        found = []
        if not self.ok or not asserted_literals:
            return found
        functions = [n for n in ast.walk(self.tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for function in functions:
            constants = {}
            for node in ast.walk(function):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                            constants[target.id] = (node.value.value, node.lineno)

            for ret in (n for n in ast.walk(function) if isinstance(n, ast.Return)):
                value = None
                if isinstance(ret.value, ast.Constant):
                    value = ret.value.value
                elif isinstance(ret.value, ast.Name) and ret.value.id in constants:
                    value = constants[ret.value.id][0]
                if value is None:
                    continue
                new_return = ret.lineno in set(added_lines)
                new_constant = (isinstance(ret.value, ast.Name)
                                and ret.value.id in constants
                                and constants[ret.value.id][1] in set(added_lines))
                if not (new_return or new_constant):
                    continue
                forms = textual_forms(value)
                if forms & set(asserted_literals):
                    found.append((ret.lineno, sorted(forms)[0],
                                  "directly" if new_return else "via a local"))
        return found

    def swallowed_handlers(self, added_lines) -> list:
        if not self.ok:
            return []
        return [handler.lineno for handler in ast.walk(self.tree)
                if isinstance(handler, ast.ExceptHandler)
                and handler.body and all(self._is_noop(s) for s in handler.body)
                and self._touches(handler, added_lines)]

    # The spellings a handler can return that make a failure look like an
    # ordinary empty result. Deliberately short: a returned variable or a call
    # is not a default, and guessing at those is how a linter starts crying wolf.
    DEFAULT_RETURN_SPELLINGS = frozenset(
        {"None", "False", "0", "0.0", "''", "{}", "[]", "()", "set()"})

    @staticmethod
    def _spelling(node) -> str:
        try:
            return ast.unparse(node).strip()
        except (AttributeError, ValueError):     # pragma: no cover - 3.10+ has unparse
            return ""

    def _default_return(self, handler) -> str:
        """The default a handler returns, or '' when it does something else."""
        body = [statement for statement in handler.body
                if not isinstance(statement, ast.Pass)]
        if len(body) != 1:
            return ""
        statement = body[0]
        if isinstance(statement, (ast.Continue, ast.Break)):
            return type(statement).__name__.lower()
        if not isinstance(statement, ast.Return):
            return ""
        if statement.value is None:
            return "None"
        spelling = self._spelling(statement.value)
        return spelling if spelling in self.DEFAULT_RETURN_SPELLINGS else ""

    def default_returning_handlers(self, added_lines) -> list:
        """Handlers that turn an error into a default value.

        `except JSONDecodeError: return {}` is the shape an empty-handler check
        misses -- the handler does something, and what it does is make a failure
        look like a legitimate empty result. The enclosing function and the
        exception are carried along so a rule can ask whether anything tests
        that path; `ast.walk` cannot answer that, because it has no parents.
        """
        found = []
        if not self.ok:
            return found

        def walk(node, function: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    walk(child, child.name)
                    continue
                if isinstance(child, ast.ExceptHandler):
                    returned = self._default_return(child)
                    if returned and self._touches(child, added_lines):
                        found.append((child.lineno, function,
                                      self._spelling(child.type) or "Exception",
                                      returned))
                walk(child, function)

        walk(self.tree, "")
        return found

    def always_equal_classes(self, added_lines) -> list:
        """`__eq__` overridden to unconditionally return True."""
        found = []
        if not self.ok:
            return found
        for node in ast.walk(self.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name != "__eq__":
                continue
            returns = [s for s in ast.walk(node) if isinstance(s, ast.Return)]
            if (len(returns) == 1 and isinstance(returns[0].value, ast.Constant)
                    and returns[0].value.value is True and self._touches(node, added_lines)):
                found.append((node.lineno, '__eq__ overridden to always return True'))
        return found

    def exit_zero_calls(self, added_lines) -> list:
        """`exit(0)` that can hide a failing suite, not the ordinary CLI kind.

        A trailing `sys.exit(0)` at the end of a CLI entry point, or any exit
        inside an `if __name__ == "__main__"` block, is ordinary code: the
        tests have already run by then, or the code never runs under a test
        runner. An exit earlier in a function, or in a helper a test may call,
        can end the session before the suite reports.
        """
        found = []
        if not self.ok:
            return found

        entry_names = {"main", "cli", "run_cli", "run_main"}
        legit_lines: set = set()

        def mark_trailing_exits(body) -> None:
            if not body:
                return
            last = body[-1]
            if (isinstance(last, ast.Expr) and isinstance(last.value, ast.Call)
                    and self._is_exit_zero(last.value)):
                legit_lines.add(last.value.lineno)

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in entry_names:
                    mark_trailing_exits(node.body)
            if isinstance(node, ast.If):
                if "__main__" in ast.unparse(node.test):
                    for stmt in ast.walk(node):
                        if isinstance(stmt, ast.Call) and self._is_exit_zero(stmt):
                            legit_lines.add(stmt.lineno)

        for call in (n for n in ast.walk(self.tree) if isinstance(n, ast.Call)):
            if not self._is_exit_zero(call) or not self._touches(call, added_lines):
                continue
            if call.lineno in legit_lines:
                continue
            func = call.func
            found.append((getattr(call, "lineno", None),
                          f"{func.value.id}.{func.attr}(0) before the end of a run can "
                          "force a suite to report success early"))
        return found

    @staticmethod
    def _is_exit_zero(call) -> bool:
        func = call.func
        return (isinstance(func, ast.Attribute) and func.attr in ("exit", "_exit")
                and isinstance(func.value, ast.Name) and func.value.id in ("sys", "os")
                and bool(call.args) and isinstance(call.args[0], ast.Constant)
                and call.args[0].value == 0)
