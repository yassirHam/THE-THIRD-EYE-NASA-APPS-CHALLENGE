"""Guard: no test function or method is defined twice in the same scope.

A second definition with the same name silently replaces the first, so the first never runs
(escalation P1-C-001-r5 item 2). This check parses the test sources; it imports nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _duplicates(tree: ast.AST) -> list[str]:
    found: list[str] = []
    scopes = [tree] + [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    for scope in scopes:
        seen: dict[str, int] = {}
        for node in getattr(scope, "body", []):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                if node.name in seen:
                    owner = getattr(scope, "name", "<module>")
                    found.append(f"{owner}.{node.name} (lines {seen[node.name]} and {node.lineno})")
                seen[node.name] = node.lineno
    return found


def test_no_test_name_is_defined_twice_in_one_scope() -> None:
    problems: list[str] = []
    for path in sorted(HERE.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        problems += [f"{path.name}: {d}" for d in _duplicates(tree)]
    assert not problems, "shadowed tests: " + "; ".join(problems)


def test_guard_detects_a_shadowed_test() -> None:
    source = "class T:\n    def test_a(self): pass\n    def test_a(self): pass\n"
    assert _duplicates(ast.parse(source)) == ["T.test_a (lines 2 and 3)"]
