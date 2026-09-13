"""AST-based checks for Python.

Regex cannot follow a value one hop away (`result = 5` then `return result`)
and breaks on a trailing comment (`return 5  # fixed`). Parsing the file and
flagging only nodes that land on added diff lines fixes both, and cuts false
positives because it reasons about structure rather than text.
"""

from __future__ import annotations

import ast

from .report import Flag


def _textual_forms(value) -> set:
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


def _line_in(added_lines, node) -> bool:
    lo = getattr(node, "lineno", None)
    if lo is None:
        return False
    hi = getattr(node, "end_lineno", lo) or lo
    return any(line in added_lines for line in range(lo, hi + 1))


def _is_noop(stmt) -> bool:
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return True
    return False


def check_python(path, added_lines, asserted_literals, is_test) -> list:
    flags: list = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError, ValueError):
        return flags

    functions = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    for fn in functions:
        consts = {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                        consts[target.id] = (node.value.value, node.lineno)

        for ret in (n for n in ast.walk(fn) if isinstance(n, ast.Return)):
            value = None
            if isinstance(ret.value, ast.Constant):
                value = ret.value.value
            elif isinstance(ret.value, ast.Name) and ret.value.id in consts:
                value = consts[ret.value.id][0]
            if value is None:
                continue
            new_return = ret.lineno in added_lines
            new_const = (isinstance(ret.value, ast.Name) and ret.value.id in consts
                         and consts[ret.value.id][1] in added_lines)
            if not (new_return or new_const):
                continue
            forms = _textual_forms(value)
            if forms & asserted_literals:
                shown = sorted(forms)[0]
                flags.append(Flag(
                    path, "hardcoded-return",
                    f"returns literal {shown} (directly or via a local), which a test "
                    f"asserts against -- check this isn't a pass-through",
                ))

    for handler in (n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)):
        if handler.body and all(_is_noop(s) for s in handler.body) and _line_in(added_lines, handler):
            flags.append(Flag(path, "swallowed-exception",
                              "except block catches and drops the error"))

    for fn in (n for n in functions if n.name == "__eq__"):
        rets = [s for s in ast.walk(fn) if isinstance(s, ast.Return)]
        if (len(rets) == 1 and isinstance(rets[0].value, ast.Constant)
                and rets[0].value.value is True and _line_in(added_lines, fn)):
            flags.append(Flag(path, "known-exploit-pattern",
                              '__eq__ overridden to unconditionally return True ("AlwaysEqual")'))

    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        fn = call.func
        if (isinstance(fn, ast.Attribute) and fn.attr in ("exit", "_exit")
                and isinstance(fn.value, ast.Name) and fn.value.id in ("sys", "os")
                and call.args and isinstance(call.args[0], ast.Constant)
                and call.args[0].value == 0 and _line_in(added_lines, call)):
            flags.append(Flag(path, "known-exploit-pattern",
                              "sys.exit(0)/os._exit(0) -- can force a suite to report success early"))

    return flags
