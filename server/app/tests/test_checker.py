from app.checker.checks import check_code, check_spec, check_stack
from app.llm.fake_data import CODE, SPEC, STACK
from app.schemas.agents import CodeBundle, GeneratedFile, ProjectSpec, StackPlan

STACK_PLAN = StackPlan.model_validate(STACK)


def f(path: str, content: str, language: str = "plaintext") -> GeneratedFile:
    return GeneratedFile(path=path, language=language, content=content, purpose="test")  # type: ignore[arg-type]


def by_name(results):
    return {r.name: r for r in results}


def test_canned_project_passes_every_check() -> None:
    results = check_code(CodeBundle.model_validate(CODE).files, STACK_PLAN)
    assert all(r.passed for r in results), [(r.name, r.details) for r in results if not r.passed]
    assert all(r.duration_ms >= 0 for r in results)


def test_syntax_errors_are_found_without_running_code() -> None:
    files = [
        f("app/main.py", "def broken(:\n    pass\n", "python"),
        f("config.json", "{not json}", "json"),
        f("ci.yml", "key: [unclosed", "yaml"),
        f("web/App.tsx", "export function App() { return (<div>) ", "typescript"),
    ]
    result = by_name(check_code(files, None))["files_parse"]
    assert not result.passed
    assert {e["file"] for e in result.details["errors"]} == {
        "app/main.py",
        "config.json",
        "ci.yml",
        "web/App.tsx",
    }


def test_undefined_names_block_but_unused_imports_only_warn() -> None:
    lint = by_name(check_code([f("a.py", "import os\n\nprint(undefined_thing)\n")], None))["python_lint"]
    assert not lint.passed
    assert any("undefined_thing" in p["error"] and p["blocking"] for p in lint.details["problems"])

    warn = by_name(check_code([f("b.py", "import os\n")], None))["python_lint"]
    assert warn.passed and warn.severity == "warning"


def test_missing_python_dependency_is_reported() -> None:
    files = [
        f("api/main.py", "import requests\nimport jwt\nfrom fastapi import FastAPI\nimport helpers\n"),
        f("api/helpers.py", "import os\n"),
        f("api/requirements.txt", "fastapi==0.1\nPyJWT>=2\n"),
    ]
    result = by_name(check_code(files, None))["python_dependencies_declared"]
    assert not result.passed
    assert [m["import"] for m in result.details["missing"]] == [
        "requests"
    ]  # jwt maps to pyjwt; helpers is local


def test_missing_npm_dependency_is_reported() -> None:
    files = [
        f("web/package.json", '{"dependencies": {"react": "19"}}', "json"),
        f(
            "web/src/App.tsx",
            "import React from 'react'\nimport axios from 'axios'\nimport { x } from './local'\n"
            "import y from '@tanstack/react-query/devtools'\nimport z from '@/lib/utils'\n",
        ),
    ]
    result = by_name(check_code(files, None))["node_dependencies_declared"]
    assert not result.passed
    assert sorted(m["package"] for m in result.details["missing"]) == ["@tanstack/react-query", "axios"]


def test_stack_mismatch_is_reported() -> None:
    files = [
        f("server.py", "from flask import Flask\napp = Flask(__name__)\n"),
        f("requirements.txt", "flask\n"),
    ]
    result = by_name(check_code(files, STACK_PLAN))["code_matches_stack"]
    assert not result.passed
    assert result.details["missing"] == ["fastapi", "react"]


def test_spec_and_stack_checks() -> None:
    assert all(r.passed for r in check_spec(ProjectSpec.model_validate(SPEC)))
    no_frontend = StackPlan.model_validate(
        {
            **STACK,
            "choices": [c for c in STACK["choices"] if c["layer"] != "frontend"],
            "frontendFramework": "none",
        }
    )
    [result] = check_stack(no_frontend)
    assert not result.passed and "frontend" in result.message
