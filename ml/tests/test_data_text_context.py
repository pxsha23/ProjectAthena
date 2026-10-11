from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from athena_advisor.data.context import (
    CONTEXT_DIM,
    CONTEXT_SCHEMA_VERSION,
    FEATURE_NAMES,
    FIELD_ORDER,
    ContextSchema,
    null_context_vector,
)
from athena_advisor.data.text import build_text, split_body


@pytest.fixture(scope="module")
def bodies() -> dict[int, tuple[str, str]]:
    path = Path(__file__).parent / "fixtures" / "stacksample_tiny" / "Questions.csv"
    questions = pd.read_csv(path)
    return {row.Id: (row.Title, row.Body) for row in questions.itertuples()}


# ---------------------------------------------------------------- text


def test_code_blocks_and_inline_code_are_removed_from_prose(bodies) -> None:
    title, body = bodies[102]
    text = build_text(title, body)
    assert "NoneType" not in text and "<" not in text
    assert (
        text == "TypeError when calling a function returned from a dict My handler crashes with this error: "
        "The dict should always contain the key."
    )
    # Inline <code> goes too: the docker command and the CMD line are not in the prose.
    assert "docker run" not in build_text(*bodies[104]) and "CMD" not in build_text(*bodies[104])


def test_whitespace_collapses_and_entities_decode() -> None:
    text = build_text("  Title\n", "<p>first&nbsp;line</p>\n\n<p>second   &amp; third</p>")
    assert text == "Title first line second & third"


def test_body_prose_is_cut_to_the_word_limit() -> None:
    body = "<p>" + " ".join(f"w{i}" for i in range(100)) + "</p>"
    text = build_text("Title", body, body_prose_words=64)
    assert text.split() == ["Title", *[f"w{i}" for i in range(64)]]


def test_split_body_keeps_code_separately(bodies) -> None:
    parts = split_body(bodies[103][1])
    assert "def login()" in parts.code and "def login()" not in parts.prose
    assert parts.has_code_block and not parts.has_link


# ---------------------------------------------------------------- context


def test_schema_shape_and_order() -> None:
    assert len(FIELD_ORDER) == 16
    assert FIELD_ORDER[0] == "has_error_trace" and FIELD_ORDER[-1] == "has_link"
    assert CONTEXT_SCHEMA_VERSION == "1.0"
    # present + 12 single values + one-hot groups of 8, 10, 9 and 3.
    assert CONTEXT_DIM == len(FEATURE_NAMES) == 1 + 12 + 8 + 10 + 9 + 3 == 43


def test_encode_one_hot_and_null_context() -> None:
    vector = ContextSchema(error_kind="syntax", code_language_guess="java", code_ratio=0.25).encode()
    assert vector.dtype == np.float32 and vector.shape == (CONTEXT_DIM,)
    assert vector[0] == 1.0  # present
    named = dict(zip(FEATURE_NAMES, vector.tolist(), strict=True))
    assert named["error_kind=syntax"] == 1.0 and named["error_kind=none"] == 0.0
    assert named["code_language_guess=java"] == 1.0 and named["code_ratio"] == 0.25
    assert named["body_length_bucket=short"] == 1.0
    for group in ("error_kind", "code_language_guess", "config_file_kind", "body_length_bucket"):
        assert sum(v for k, v in named.items() if k.startswith(group + "=")) == 1.0

    null = null_context_vector()
    assert null.shape == (CONTEXT_DIM,) and not null.any()


def test_invalid_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        ContextSchema(error_kind="explosion")
    with pytest.raises(ValueError):
        ContextSchema(code_ratio=1.5)


def test_context_on_known_bodies(bodies) -> None:
    ctx = {qid: ContextSchema.from_stackoverflow_body(body) for qid, (_, body) in bodies.items()}

    assert ctx[102].has_error_trace and ctx[102].error_kind == "type" and ctx[102].has_code_block
    assert ctx[103].code_language_guess == "python" and ctx[103].mentions_test
    assert ctx[103].error_kind == "none"  # an expected 401 in a test is not a failure
    assert ctx[104].config_file_kind == "dockerfile" and ctx[104].mentions_config_file
    assert ctx[104].mentions_port_or_url and ctx[104].mentions_deploy_or_server
    assert ctx[104].code_language_guess == "shell" and not ctx[104].has_code_block  # inline code only
    assert ctx[106].config_file_kind == "nginx" and ctx[106].error_kind == "network_or_http"
    assert ctx[101].mentions_database and ctx[101].asks_comparison and not ctx[101].has_code_block
    assert ctx[107].code_language_guess == "javascript"
    for c in ctx.values():
        assert c.body_length_bucket == "short" and 0.0 <= c.code_ratio < 1.0


def test_context_rules_on_crafted_bodies() -> None:
    trace = (
        "<pre><code>Traceback (most recent call last):\n"
        "ModuleNotFoundError: No module named 'flask'</code></pre>"
    )
    c = ContextSchema.from_stackoverflow_body(trace)
    assert c.has_error_trace and c.error_kind == "import_or_module" and c.code_ratio == 1.0

    c = ContextSchema.from_stackoverflow_body(
        "<p>See <a href='https://example.com'>the docs</a> for .env files</p>"
    )
    assert c.has_link and c.config_file_kind == "env" and c.error_kind == "none"

    long_body = "<p>" + "word " * 400 + "</p>"
    assert ContextSchema.from_stackoverflow_body(long_body).body_length_bucket == "long"
    assert ContextSchema.from_stackoverflow_body("").encode()[0] == 1.0


def test_athena_state_is_not_built_yet() -> None:
    with pytest.raises(NotImplementedError):
        ContextSchema.from_athena_state({})
