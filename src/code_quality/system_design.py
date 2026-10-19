"""Deterministic structure checks; semantic design review remains an agent responsibility."""

import ast
from dataclasses import asdict, dataclass
from pathlib import Path

EXCLUDED_DIRECTORIES = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "data", ".idea"}
MAX_FUNCTION_LINES = 60
MAX_COGNITIVE_COMPLEXITY = 15
MAX_NESTING_DEPTH = 3
AMBIGUOUS_NAMES = {"do_stuff", "handle", "process", "manage", "utils", "helper", "party"}
CONTROL_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.Match)


@dataclass(frozen=True)
class ReviewFinding:
    path: str
    line: int
    rule: str
    message: str


class CognitiveVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.score = 0
        self.depth = 0
        self.max_depth = 0

    def generic_visit(self, node: ast.AST) -> None:
        is_control = isinstance(node, CONTROL_NODES)
        if isinstance(node, ast.BoolOp):
            self.score += len(node.values) - 1
        if is_control:
            self.score += 1 + self.depth
            self.depth += 1
            self.max_depth = max(self.max_depth, self.depth)
        super().generic_visit(node)
        if is_control:
            self.depth -= 1


def review_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef, path: Path
) -> list[ReviewFinding]:
    visitor = CognitiveVisitor()
    for statement in node.body:
        visitor.visit(statement)
    metrics = (
        (node.end_lineno - node.lineno + 1, MAX_FUNCTION_LINES, "function_length"),
        (visitor.score, MAX_COGNITIVE_COMPLEXITY, "cognitive_complexity"),
        (visitor.max_depth, MAX_NESTING_DEPTH, "nesting_depth"),
    )
    findings = [
        ReviewFinding(str(path), node.lineno, rule, f"{node.name}: {value} exceeds limit {limit}")
        for value, limit, rule in metrics
        if value > limit
    ]
    if node.name in AMBIGUOUS_NAMES:
        findings.append(
            ReviewFinding(
                str(path), node.lineno, "explicit_naming", f"Rename ambiguous function {node.name}"
            )
        )
    return findings


def review_layer_boundaries(tree: ast.AST, path: Path) -> list[ReviewFinding]:
    if path.name not in {"normalization.py", "scalars.py", "contracts.py", "existence.py"}:
        return []
    forbidden = {"psycopg", "httpx", "sqlite3", "subprocess"}
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)]
    findings = []
    for node in imports:
        modules = (
            [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
        )
        if any(module and module.split(".")[0] in forbidden for module in modules):
            findings.append(
                ReviewFinding(
                    str(path),
                    node.lineno,
                    "layer_boundary",
                    "Domain validation must not access infrastructure",
                )
            )
    return findings


def review_python_file(path: Path) -> list[ReviewFinding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        return [ReviewFinding(str(path), error.lineno or 1, "syntax", "Invalid Python syntax")]
    functions = [
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    findings = review_layer_boundaries(tree, path)
    for function in functions:
        findings.extend(review_function(function, path))
    return findings


def find_project_code(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if not EXCLUDED_DIRECTORIES.intersection(path.relative_to(root).parts)
    ]


def review_project(root: Path) -> list[dict]:
    findings = []
    for path in find_project_code(root):
        findings.extend(asdict(finding) for finding in review_python_file(path))
    return findings
