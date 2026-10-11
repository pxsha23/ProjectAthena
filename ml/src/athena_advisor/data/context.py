"""Context features: 16 facts about a question's situation, shared by training and the live platform.

For training they are read from the Stack Overflow question body with simple keyword and regex rules
(documented next to each rule). In Athena the same fields will be filled from the project state.
Both sides produce the same vector, so the model learns from one and runs on the other.
Tags are never used here.

Vector layout (encode()): position 0 is a `present` flag (1 for a real context, 0 for the null context),
then each field in FIELD_ORDER: booleans as 0/1, code_ratio as a number in [0, 1], and categories one-hot.
"""

import re
from dataclasses import dataclass, fields
from typing import Any

import numpy as np

from athena_advisor.data.text import split_body

CONTEXT_SCHEMA_VERSION = "1.0"

ERROR_KINDS = (
    "none",
    "type",
    "syntax",
    "import_or_module",
    "network_or_http",
    "permission",
    "null_or_undefined",
    "other",
)
CODE_LANGUAGES = (
    "none",
    "python",
    "javascript",
    "typescript",
    "java",
    "csharp",
    "php",
    "sql",
    "shell",
    "other",
)
CONFIG_FILE_KINDS = (
    "none",
    "dockerfile",
    "compose",
    "package_json",
    "requirements",
    "ci_yaml",
    "nginx",
    "env",
    "other",
)
BODY_LENGTH_BUCKETS = ("short", "medium", "long")

CATEGORIES: dict[str, tuple[str, ...]] = {
    "error_kind": ERROR_KINDS,
    "code_language_guess": CODE_LANGUAGES,
    "config_file_kind": CONFIG_FILE_KINDS,
    "body_length_bucket": BODY_LENGTH_BUCKETS,
}

# Word counts (prose plus code) that separate the length buckets.
SHORT_MAX_WORDS = 100
MEDIUM_MAX_WORDS = 300


@dataclass(frozen=True)
class ContextSchema:
    has_error_trace: bool = False
    error_kind: str = "none"
    code_language_guess: str = "none"
    has_code_block: bool = False
    code_ratio: float = 0.0
    mentions_config_file: bool = False
    config_file_kind: str = "none"
    mentions_test: bool = False
    mentions_port_or_url: bool = False
    mentions_install_or_dependency: bool = False
    mentions_database: bool = False
    mentions_ui_or_browser: bool = False
    mentions_deploy_or_server: bool = False
    asks_comparison: bool = False
    body_length_bucket: str = "short"
    has_link: bool = False

    def __post_init__(self) -> None:
        for name, allowed in CATEGORIES.items():
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {allowed}, got {getattr(self, name)!r}")
        if not 0.0 <= self.code_ratio <= 1.0:
            raise ValueError("code_ratio must be between 0 and 1")

    def encode(self) -> np.ndarray:
        """The float32 vector the model reads, with the present flag set to 1."""
        values: list[float] = [1.0]
        for name in FIELD_ORDER:
            value = getattr(self, name)
            if name in CATEGORIES:
                values.extend(1.0 if value == option else 0.0 for option in CATEGORIES[name])
            else:
                values.append(float(value))
        return np.asarray(values, dtype=np.float32)

    @classmethod
    def from_stackoverflow_body(cls, html: str) -> "ContextSchema":
        """Fills every field from a question body (HTML) with the rules below. Tags are never used."""
        parts = split_body(html)
        prose, code = parts.prose, parts.code
        everything = f"{prose}\n{code}"
        low = everything.lower()

        prose_chars, code_chars = len(prose), len(code.strip())
        words = len(everything.split())
        kind = _error_kind(everything)
        has_trace = _has_error_trace(everything)
        config_kind = _config_file_kind(low)
        return cls(
            has_error_trace=has_trace,
            # A named error with no recognised class still counts as "other".
            error_kind=kind if kind != "none" else ("other" if has_trace else "none"),
            code_language_guess=_code_language(code),
            has_code_block=parts.has_code_block,
            code_ratio=round(code_chars / (code_chars + prose_chars), 4) if code_chars + prose_chars else 0.0,
            mentions_config_file=config_kind != "none",
            config_file_kind=config_kind,
            mentions_test=bool(_TEST.search(low)),
            mentions_port_or_url=bool(_PORT_OR_URL.search(low)),
            mentions_install_or_dependency=bool(_INSTALL.search(low)),
            mentions_database=bool(_DATABASE.search(low)),
            mentions_ui_or_browser=bool(_UI.search(low)),
            mentions_deploy_or_server=bool(_DEPLOY.search(low)),
            asks_comparison=bool(_COMPARISON.search(prose.lower())),
            body_length_bucket="short"
            if words <= SHORT_MAX_WORDS
            else "medium"
            if words <= MEDIUM_MAX_WORDS
            else "long",
            has_link=parts.has_link or bool(_URL.search(low)),
        )

    @classmethod
    def from_athena_state(cls, state: dict[str, Any]) -> "ContextSchema":
        """Fills the same fields from an Athena project, so the live model sees what it was trained on.

        Planned mapping (to be built with the platform integration):
        - has_error_trace, error_kind: from the latest failing consistency check or a pasted error in the
          message (same error rules as from_stackoverflow_body).
        - code_language_guess: from the open file's language, else the stack's backend language.
        - has_code_block, code_ratio: from the chat message (code fences versus prose).
        - mentions_config_file, config_file_kind: the open file when it is a Dockerfile, compose file,
          package.json, requirements.txt, CI workflow, nginx config or .env.
        - mentions_test: EVA findings exist, or the open file is a test file.
        - mentions_port_or_url, mentions_deploy_or_server: the project is at the deploy stage, or the
          deployment bundle has targets.
        - mentions_install_or_dependency: a failing dependency check (python or node dependencies declared).
        - mentions_database: the stack plan has a database.
        - mentions_ui_or_browser: the stack plan has a frontend and the open file is a frontend file.
        - asks_comparison, body_length_bucket, has_link: from the chat message text with the same rules.
        """
        raise NotImplementedError("from_athena_state is built with the platform integration")


FIELD_ORDER: tuple[str, ...] = tuple(f.name for f in fields(ContextSchema))
FEATURE_NAMES: tuple[str, ...] = ("present",) + tuple(
    feature
    for name in FIELD_ORDER
    for feature in ([f"{name}={option}" for option in CATEGORIES[name]] if name in CATEGORIES else [name])
)
CONTEXT_DIM = len(FEATURE_NAMES)


def null_context_vector() -> np.ndarray:
    """No context at all: every value is 0, including the present flag (FiLM then does nothing)."""
    return np.zeros(CONTEXT_DIM, dtype=np.float32)


# ---------------------------------------------------------------- rules
# Each rule is a plain regular expression, run on the lowercased body unless noted.

# A stack trace or a named error: Python tracebacks, "SomethingError: ...", "SomethingException",
# Java-style "at com.example.Foo(Foo.java:12)" frames, and JavaScript "Uncaught" errors.
_TRACE = re.compile(
    r"(?i:traceback \(most recent call last\))|\b[A-Z]\w*(?:Error|Exception)\b\s*:"
    r"|\bException in thread\b|^\s*at [\w.$<>]+\(.*\)\s*$|(?i:\buncaught\b)|(?i:\bstack ?trace\b)",
    re.MULTILINE,
)
# Error classes are only looked for when the body talks about a failure at all: a trace, an error word,
# or an HTTP error status phrased as a failure ("gives 502", "getting 404", "500 Internal Server Error").
# Without this, a deploy question that merely mentions "ssl" would get an error kind, and a test that
# expects a 401 would look like a failure.
_FAILURE = re.compile(
    r"\b(?:errors?|exceptions?|fail(?:s|ed|ure|ing)?|crash(?:es|ed)?|refused|denied|broken)\b"
    r"|\b(?:gives?|getting|got|throws?)\s+(?:an?\s+)?[45]\d\d\b"
    r"|\b[45]\d\d\s+(?:bad gateway|not found|forbidden|unauthorized|internal server error"
    r"|service unavailable)\b",
    re.IGNORECASE,
)

# Error classes, checked in this order: the named exception class decides, so Python's
# "TypeError: 'NoneType' object is not callable" is a type error, not a null error.
_ERROR_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "import_or_module",
        re.compile(
            r"importerror|modulenotfounderror|no module named|cannot find module|module not found"
            r"|classnotfoundexception|noclassdeffounderror|unresolved import",
            re.IGNORECASE,
        ),
    ),
    (
        "syntax",
        re.compile(r"syntaxerror|syntax error|unexpected token|parse error|parseerror", re.IGNORECASE),
    ),
    ("type", re.compile(r"typeerror|classcastexception|type mismatch|invalidcastexception", re.IGNORECASE)),
    (
        "null_or_undefined",
        re.compile(
            r"nullpointerexception|nullreferenceexception|nonetype|is undefined|of undefined|of null"
            r"|undefined is not",
            re.IGNORECASE,
        ),
    ),
    (
        "network_or_http",
        re.compile(
            r"econnrefused|connection refused|connectionerror|timed out|timeout|bad gateway"
            r"|\b(?:400|401|403|404|405|408|429|500|502|503|504)\b|cors|ssl|getaddrinfo",
            re.IGNORECASE,
        ),
    ),
    (
        "permission",
        re.compile(r"permissionerror|permission denied|eacces|access denied|unauthorizedaccess", re.I),
    ),
)

# Language guess from the code only: count characteristic markers and take the most frequent language.
_LANGUAGE_MARKERS: dict[str, re.Pattern[str]] = {
    "python": re.compile(
        r"^\s*def \w+\(|^\s*import \w+|^\s*from [\w.]+ import|\bprint\(|\bself\.|^\s*@\w+|\belif\b|:\s*$",
        re.MULTILINE,
    ),
    "typescript": re.compile(
        r":\s*(?:string|number|boolean|any)\b|\binterface \w+\s*\{|<\w+>\(|\bas const\b"
    ),
    "javascript": re.compile(
        r"\bfunction\b|\bconst \w+\s*=|\blet \w+\s*=|=>|console\.log|\brequire\(|document\.|\bset\w+\("
    ),
    "java": re.compile(r"public static void|System\.out\.|public class|private \w+ \w+;|@Override"),
    "csharp": re.compile(r"\busing System|Console\.Write|\bnamespace \w+|public async Task|\bvar \w+ = new"),
    "php": re.compile(r"<\?php|\$this->|\becho \$|\$_(?:GET|POST)"),
    "sql": re.compile(
        r"\bselect\b.+\bfrom\b|\binsert into\b|\bcreate table\b|\bupdate \w+ set\b", re.IGNORECASE
    ),
    "shell": re.compile(
        r"^\s*\$ |^\s*sudo |\bapt(?:-get)? install|\bnpm (?:install|run)|\bpip install|\bdocker run|^\s*cd ",
        re.MULTILINE,
    ),
}

# Config files, checked in this order; the first match decides the kind.
_CONFIG_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("compose", re.compile(r"docker-compose|compose\.ya?ml")),
    ("dockerfile", re.compile(r"\bdockerfile\b")),
    ("package_json", re.compile(r"package\.json")),
    ("requirements", re.compile(r"requirements\.txt|pyproject\.toml|\bpipfile\b|setup\.py")),
    (
        "ci_yaml",
        re.compile(r"\.github/workflows|\.gitlab-ci|travis\.yml|circleci|jenkinsfile|azure-pipelines"),
    ),
    ("nginx", re.compile(r"nginx\.conf|sites-available|sites-enabled")),
    ("env", re.compile(r"(?<![\w.])\.env\b|environment variables?")),
    ("other", re.compile(r"\b[\w-]+\.(?:ya?ml|toml|ini|cfg|conf|properties)\b|web\.config|settings\.py")),
)

_TEST = re.compile(r"\b(?:tests?|testing|unit ?tests?|pytest|jest|junit|mocha|selenium|cypress|assert\w*)\b")
_URL = re.compile(r"https?://")
_PORT_OR_URL = re.compile(r"\bport\s*:?\s*\d{2,5}\b|localhost|127\.0\.0\.1|0\.0\.0\.0|:\d{4,5}\b|https?://")
_INSTALL = re.compile(
    r"\b(?:install(?:ed|ing)?|dependenc(?:y|ies)|packages?|npm|pip|maven|gradle|upgrade[ds]?|versions?)\b"
)
_DATABASE = re.compile(
    r"\b(?:database|db|sql|mysql|postgres(?:ql)?|mongo(?:db)?|sqlite|tables?|query|queries|orm|redis)\b"
)
_UI = re.compile(
    r"\b(?:browser|button|page|css|html|ui|screens?|click(?:s|ed)?|forms?|layout|chrome|firefox|mobile)\b"
)
_DEPLOY = re.compile(
    r"\b(?:deploy(?:ed|ing|ment)?|servers?|production|hosting|heroku|aws|azure|nginx|apache|docker"
    r"|containers?|kubernetes|vps)\b"
)
# Run on the prose only: a question that weighs options against each other.
_COMPARISON = re.compile(
    r"\b(?:vs\.?|versus|better|best way|difference between|compare[ds]?|comparison|which (?:one|is|should))\b"
    r"|\bshould i use\b|\bor\b[^.?!]{0,40}\?"
)


def _has_error_trace(text: str) -> bool:
    return bool(_TRACE.search(text))


def _error_kind(text: str) -> str:
    if not (_has_error_trace(text) or _FAILURE.search(text)):
        return "none"
    for kind, pattern in _ERROR_RULES:
        if pattern.search(text):
            return kind
    return "none"


def _code_language(code: str) -> str:
    if not code.strip():
        return "none"
    scores = {lang: len(pattern.findall(code)) for lang, pattern in _LANGUAGE_MARKERS.items()}
    best = max(scores.values())
    if best == 0:
        return "other"
    # Ties resolve by the dictionary order above (typescript before javascript: TS is a JS superset).
    return next(lang for lang, score in scores.items() if score == best)


def _config_file_kind(low: str) -> str:
    for kind, pattern in _CONFIG_RULES:
        if pattern.search(low):
            return kind
    return "none"
