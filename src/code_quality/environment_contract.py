"""Validate documented configuration names without reading credential values."""

import ast
from pathlib import Path

ENVIRONMENT_NAMES = frozenset(
    {
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_STORAGE_URL",
        "SUPABASE_STORAGE_KEY",
        "SUPABASE_PROJECT_ID",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SE_LIGA_BRASIL_IDENTITY_KEY",
        "TEST_DATABASE_URL",
        "SE_LIGA_BRASIL_TEST_ENV_FILE",
    }
)


def read_template_names(path: Path) -> set[str]:
    names = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or name not in ENVIRONMENT_NAMES or name in names or value.strip():
            raise ValueError(f"Invalid or populated environment template entry at line {number}")
        names.add(name)
    return names


def referenced_environment_names(root: Path) -> set[str]:
    names = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names.update(literal_environment_names(tree))
    return names


def literal_environment_names(tree: ast.AST) -> set[str]:
    names = set()
    aliases = environment_import_aliases(tree)
    for node in ast.walk(tree):
        value = environment_read_literal(node, aliases)
        if value is not None:
            names.add(value)
    return names


def environment_import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update(
                {item.asname or item.name: "os" for item in node.names if item.name == "os"}
            )
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            aliases.update(
                {
                    item.asname or item.name: "os." + item.name
                    for item in node.names
                    if item.name in {"getenv", "environ"}
                }
            )
    return aliases


def environment_accessor(node: ast.AST, aliases: dict[str, str]) -> str:
    first, separator, rest = ast.unparse(node).partition(".")
    return aliases.get(first, first) + (separator + rest if separator else "")


def environment_read_literal(node: ast.AST, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Subscript):
        if environment_accessor(node.value, aliases) != "os.environ":
            return None
        argument = node.slice
        accessor = "os.environ"
    elif isinstance(node, ast.Call):
        accessor = environment_accessor(node.func, aliases)
        if accessor not in {"os.getenv", "os.environ.get", "values.get"}:
            return None
        argument = (
            node.args[0]
            if node.args
            else next(
                (item.value for item in node.keywords if item.arg == "key"),
                None,
            )
        )
    else:
        return None
    if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
        return None
    if accessor == "values.get" and not argument.value.isupper():
        return None
    return argument.value


def validate_environment_template(root: Path) -> None:
    names = read_template_names(root / ".env.example")
    missing = (ENVIRONMENT_NAMES | referenced_environment_names(root / "src")) - names
    if missing:
        raise ValueError("Undocumented environment variable names: " + ", ".join(sorted(missing)))
