"""Static heuristic detector for Assertion Roulette (AST only, no execution)."""

from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


@dataclass
class AssertInfo:
    line: int
    has_msg: bool


@dataclass
class TestFunctionReport:
    name: str
    lineno: int
    total_asserts: int
    unlabeled_asserts: int
    labeled_asserts: int
    ar_candidate: bool
    asserts: list[AssertInfo]


@dataclass
class FileReport:
    path: str
    status: str  # ok | parse_error
    error: str | None
    tests: list[TestFunctionReport]
    ar_flagged_tests: int
    ar_unlabeled_asserts: int
    ar_total_asserts: int


def _is_test_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return node.name.startswith("test_")


def _collect_test_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Collect test functions including methods inside Test* classes, excluding nested defs attribution."""
    result: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef):
            if node.name.startswith("Test"):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_test_func(item):
                        result.append(item)
            # Do not recurse into classes for nested? We still want top-level.
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef):
            if _is_test_func(node):
                # only top-level (parent module) — but visitor visits all; filter by checking parent? 
                # We'll collect and dedupe by id later; here collect all top-level via Module handling.
                pass
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            self.generic_visit(node)

    # Simpler: walk module body for top-level functions and Test* classes.
    if isinstance(tree, ast.Module):
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_test_func(node):
                result.append(node)
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_test_func(item):
                        result.append(item)
    return result


def _count_asserts(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, int, list[AssertInfo]]:
    """Count ast.Assert in the function body, excluding nested function definitions."""
    total = 0
    unlabeled = 0
    infos: list[AssertInfo] = []

    class Counter(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            # skip nested functions
            if node is not func:
                return
            # We handle manually below; this visitor not used for recursion into nested
            pass

    # Walk but stop at nested function defs
    def walk(node, in_nested=False):
        nonlocal total, unlabeled
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and node is not func:
            # skip entire nested function
            return
        if isinstance(node, ast.Assert):
            total += 1
            has_msg = node.msg is not None
            if not has_msg:
                unlabeled += 1
            infos.append(AssertInfo(line=node.lineno, has_msg=has_msg))
            return
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(func)
    return total, unlabeled, infos


def analyze_source(source: str, path: str = "<string>") -> FileReport:
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return FileReport(
            path=path,
            status="parse_error",
            error=f"SyntaxError: {e.msg} at line {e.lineno}",
            tests=[],
            ar_flagged_tests=0,
            ar_unlabeled_asserts=0,
            ar_total_asserts=0,
        )
    tests: list[TestFunctionReport] = []
    for func in _collect_test_functions(tree):
        total, unlabeled, infos = _count_asserts(func)
        tests.append(TestFunctionReport(
            name=func.name,
            lineno=func.lineno,
            total_asserts=total,
            unlabeled_asserts=unlabeled,
            labeled_asserts=total - unlabeled,
            ar_candidate=unlabeled >= 2,
            asserts=[asdict(a) for a in infos],
        ))
    flagged = sum(1 for t in tests if t.ar_candidate)
    unl_total = sum(t.unlabeled_asserts for t in tests)
    tot_total = sum(t.total_asserts for t in tests)
    return FileReport(
        path=path,
        status="ok",
        error=None,
        tests=tests,
        ar_flagged_tests=flagged,
        ar_unlabeled_asserts=unl_total,
        ar_total_asserts=tot_total,
    )


def analyze_file(path: str | Path) -> FileReport:
    p = Path(path)
    source = p.read_text(encoding="utf-8")
    return analyze_source(source, str(p))


def analyze_files(paths: Iterable[str | Path]) -> list[FileReport]:
    return [analyze_file(p) for p in paths]


def summary(reports: list[FileReport]) -> dict:
    return {
        "files": len(reports),
        "parse_errors": sum(1 for r in reports if r.status == "parse_error"),
        "ar_flagged_tests": sum(r.ar_flagged_tests for r in reports),
        "ar_unlabeled_asserts": sum(r.ar_unlabeled_asserts for r in reports),
        "ar_total_asserts": sum(r.ar_total_asserts for r in reports),
    }
