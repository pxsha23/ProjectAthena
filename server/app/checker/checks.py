"""Static consistency checks between agent outputs.

Nothing here executes generated code: Python is parsed with `ast`, linted with pyflakes (which also only
parses), and other files are parsed as data (JSON / YAML / TOML) or scanned with regular expressions.
"""

import ast
import functools
import json
import re
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Literal, ParamSpec, TypeVar

import yaml
from pyflakes import checker as pyflakes_checker
from pyflakes import messages as pyflakes_messages

from app.schemas.agents import GeneratedFile, ProjectSpec, StackPlan

Severity = Literal["info", "warning", "error"]


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: Severity
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


P = ParamSpec("P")
R = TypeVar("R")


def timed(fn: Callable[P, R]) -> Callable[P, R]:
    """Records how long each check took on the CheckResult(s) it returns (for the papers)."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        started = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000
        items = result if isinstance(result, list) else [result] if result is not None else []
        for item in items:
            item.duration_ms = elapsed / len(items)
        return result

    return wrapper


# Import name -> PyPI package name, where they differ.
IMPORT_TO_PACKAGE = {
    "jwt": "pyjwt",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "jose": "python-jose",
    "multipart": "python-multipart",
    "dateutil": "python-dateutil",
    "psycopg2": "psycopg2-binary",
    "google": "google-api-python-client",
    "attr": "attrs",
}
# Packages that ship without being listed because another listed package pulls them in.
IMPLIED_BY = {"pydantic": {"fastapi"}, "starlette": {"fastapi"}, "werkzeug": {"flask"}, "jinja2": {"flask"}}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ---------------------------------------------------------------- spec / stack


@timed
def check_spec(spec: ProjectSpec) -> list[CheckResult]:
    core = next((s for s in spec.sections if s.title.lower().startswith("core features")), None)
    results = [
        CheckResult(
            "spec_has_core_features",
            core is not None and len(core.items) >= 1,
            "error",
            "Spec lists core features" if core else 'Spec has no "Core features" section',
            {"count": len(core.items) if core else 0},
        ),
        CheckResult(
            "spec_has_target_users",
            len(spec.target_users) >= 1,
            "error",
            f"Spec names {len(spec.target_users)} target user group(s)",
        ),
    ]
    return results


@timed
def check_stack(stack: StackPlan) -> list[CheckResult]:
    layers = {c.layer for c in stack.choices}
    missing = [layer for layer in ("frontend", "backend") if layer not in layers]
    return [
        CheckResult(
            "stack_covers_layers",
            not missing,
            "warning",
            "Stack covers frontend and backend" if not missing else f"Stack has no choice for: {missing}",
            {"layers": sorted(layers)},
        )
    ]


# ---------------------------------------------------------------- code


@timed
def _check_syntax(files: list[GeneratedFile]) -> CheckResult:
    errors: list[dict[str, Any]] = []
    parsers: dict[str, Callable[[str], Any]] = {
        ".json": json.loads,
        ".yml": yaml.safe_load,
        ".yaml": yaml.safe_load,
        ".toml": tomllib.loads,
    }
    for f in files:
        suffix = PurePosixPath(f.path).suffix
        try:
            if suffix == ".py":
                ast.parse(f.content, filename=f.path)
            elif suffix in parsers:
                parsers[suffix](f.content)
            elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
                _check_brackets(f.content)
        except (SyntaxError, ValueError, yaml.YAMLError, tomllib.TOMLDecodeError) as exc:
            line = getattr(exc, "lineno", None)
            errors.append({"file": f.path, "line": line, "error": str(exc).splitlines()[0][:300]})
    return CheckResult(
        "files_parse",
        not errors,
        "error",
        "All files parse" if not errors else f"{len(errors)} file(s) have syntax errors",
        {"errors": errors},
    )


def _check_brackets(source: str) -> None:
    """Very small sanity check for JS/TS: brackets balance outside strings and comments."""
    stripped = re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)
    stripped = re.sub(r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"|`(?:\\.|[^`\\])*`", "''", stripped)
    pairs, stack = {")": "(", "]": "[", "}": "{"}, []
    for i, ch in enumerate(stripped):
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                raise ValueError(f"unbalanced '{ch}' near character {i}")
    if stack:
        raise ValueError(f"unclosed '{stack[-1]}'")


@timed
def _check_python_lint(files: list[GeneratedFile]) -> CheckResult:
    problems: list[dict[str, Any]] = []
    blocking = (pyflakes_messages.UndefinedName, pyflakes_messages.UndefinedLocal)
    for f in files:
        if not f.path.endswith(".py"):
            continue
        try:
            tree = ast.parse(f.content, filename=f.path)
        except SyntaxError:
            continue  # reported by files_parse
        for msg in pyflakes_checker.Checker(tree, filename=f.path).messages:
            problems.append(
                {
                    "file": f.path,
                    "line": msg.lineno,
                    "error": msg.message % msg.message_args,
                    "blocking": isinstance(msg, blocking),
                }
            )
    blocking_count = sum(p["blocking"] for p in problems)
    return CheckResult(
        "python_lint",
        blocking_count == 0,
        "error" if blocking_count else "warning" if problems else "info",
        "No lint problems" if not problems else f"{len(problems)} lint problem(s), {blocking_count} blocking",
        {"problems": problems},
    )


def _python_imports(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _requirements(files: list[GeneratedFile]) -> set[str] | None:
    declared: set[str] = set()
    found = False
    for f in files:
        name = PurePosixPath(f.path).name
        if name == "requirements.txt":
            found = True
            for line in f.content.splitlines():
                line = line.split("#", 1)[0].strip()
                if line and not line.startswith("-"):
                    declared.add(_normalize(re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0]))
        elif name == "pyproject.toml":
            try:
                data = tomllib.loads(f.content)
            except tomllib.TOMLDecodeError:
                continue
            found = True
            for dep in data.get("project", {}).get("dependencies", []):
                declared.add(_normalize(re.split(r"[<>=!~\[; ]", dep, maxsplit=1)[0]))
    return declared if found else None


@timed
def _check_python_dependencies(files: list[GeneratedFile]) -> CheckResult | None:
    py_files = [f for f in files if f.path.endswith(".py")]
    if not py_files:
        return None
    declared = _requirements(files)
    local = {PurePosixPath(f.path).stem for f in py_files} | {
        part for f in py_files for part in PurePosixPath(f.path).parts[:-1]
    }
    third_party: dict[str, list[str]] = {}
    for f in py_files:
        for name in _python_imports(f.content):
            if name in sys.stdlib_module_names or name in local or name == "__future__":
                continue
            third_party.setdefault(name, []).append(f.path)

    if declared is None:
        return CheckResult(
            "python_dependencies_declared",
            not third_party,
            "error",
            "No requirements.txt or pyproject.toml, but the code imports third-party packages"
            if third_party
            else "No third-party Python imports",
            {"imports": sorted(third_party)},
        )

    missing = []
    for name, used_in in sorted(third_party.items()):
        package = _normalize(IMPORT_TO_PACKAGE.get(name, name))
        implied = IMPLIED_BY.get(name, set())
        if package not in declared and not (implied & declared):
            missing.append({"import": name, "package": package, "usedIn": sorted(set(used_in))})
    return CheckResult(
        "python_dependencies_declared",
        not missing,
        "error",
        "Every Python import is declared"
        if not missing
        else f"{len(missing)} import(s) missing from requirements",
        {"missing": missing, "declared": sorted(declared)},
    )


NODE_BUILTINS = {
    "fs",
    "path",
    "http",
    "https",
    "crypto",
    "os",
    "url",
    "util",
    "events",
    "stream",
    "child_process",
}
IMPORT_RE = re.compile(r"""(?:import\s[^'"]*?from\s*|import\s*\(?\s*|require\(\s*)['"]([^'"]+)['"]""")


def _node_package(spec: str) -> str | None:
    if spec.startswith((".", "/", "@/", "~/", "node:")) or spec in NODE_BUILTINS:
        return None
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") else parts[0]


@timed
def _check_node_dependencies(files: list[GeneratedFile]) -> CheckResult | None:
    js_files = [f for f in files if PurePosixPath(f.path).suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs"}]
    if not js_files:
        return None
    manifests: dict[str, set[str]] = {}
    for f in files:
        if PurePosixPath(f.path).name == "package.json":
            try:
                data = json.loads(f.content)
            except json.JSONDecodeError:
                continue
            deps = set(data.get("dependencies", {})) | set(data.get("devDependencies", {}))
            manifests[str(PurePosixPath(f.path).parent)] = deps

    missing = []
    for f in js_files:
        # Nearest package.json above the file.
        owner = next(
            (d for d in sorted(manifests, key=len, reverse=True) if d == "." or f.path.startswith(d + "/")),
            None,
        )
        declared = manifests.get(owner, set()) if owner else set()
        for spec in IMPORT_RE.findall(f.content):
            package = _node_package(spec)
            if package and package not in declared and not package.startswith("@types/"):
                missing.append({"file": f.path, "package": package, "manifest": owner})
    return CheckResult(
        "node_dependencies_declared",
        not missing,
        "error",
        "Every npm import is declared"
        if not missing
        else f"{len(missing)} npm import(s) missing from package.json",
        {"missing": missing},
    )


FRAMEWORK_EVIDENCE: dict[str, Callable[[list[GeneratedFile]], bool]] = {
    "fastapi": lambda fs: any("fastapi" in _python_imports(f.content) for f in fs if f.path.endswith(".py")),
    "flask": lambda fs: any("flask" in _python_imports(f.content) for f in fs if f.path.endswith(".py")),
    "django": lambda fs: any("django" in _python_imports(f.content) for f in fs if f.path.endswith(".py")),
    "express": lambda fs: any(re.search(r"""['"]express['"]""", f.content) for f in fs),
    "react": lambda fs: any(re.search(r"""from\s+['"]react['"]|"react"\s*:""", f.content) for f in fs),
    "vue": lambda fs: any(f.path.endswith(".vue") or '"vue"' in f.content for f in fs),
    "svelte": lambda fs: any(f.path.endswith(".svelte") for f in fs),
    "nextjs": lambda fs: any('"next"' in f.content for f in fs if f.path.endswith("package.json")),
}


@timed
def _check_stack_matches_code(stack: StackPlan, files: list[GeneratedFile]) -> CheckResult:
    expected = [fw for fw in (stack.backend_framework, stack.frontend_framework) if fw != "none"]
    missing = [fw for fw in expected if fw in FRAMEWORK_EVIDENCE and not FRAMEWORK_EVIDENCE[fw](files)]
    return CheckResult(
        "code_matches_stack",
        not missing,
        "error",
        "Code uses the chosen frameworks"
        if not missing
        else f"No code found for chosen framework(s): {missing}",
        {"expected": expected, "missing": missing},
    )


def check_code(files: list[GeneratedFile], stack: StackPlan | None) -> list[CheckResult]:
    results = [_check_syntax(files), _check_python_lint(files)]
    for optional in (_check_python_dependencies(files), _check_node_dependencies(files)):
        if optional is not None:
            results.append(optional)
    if stack is not None:
        results.append(_check_stack_matches_code(stack, files))
    return results


def check_deployment(files: list[GeneratedFile]) -> list[CheckResult]:
    deploy_files = [
        f for f in files if f.path in {"docker-compose.yml", "render.yaml", ".github/workflows/deploy.yml"}
    ]
    result = _check_syntax(deploy_files)
    result.name = "deployment_files_parse"
    return [result]
