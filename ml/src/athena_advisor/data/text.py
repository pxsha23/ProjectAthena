"""Model input text: the title plus the first words of the body's prose.

The body is HTML. Code (<pre> blocks and inline <code>) is removed from the prose, because the model input
should describe the question in words; the code is summarised separately by the context features.
Tags are never part of the text: these functions only ever receive the title and the body.
"""

import re
import warnings
from dataclasses import dataclass

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

# Bodies that happen to look like a URL or a file name make BeautifulSoup warn; they are still parsed.
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class BodyParts:
    prose: str  # body text with all code removed, whitespace collapsed
    code: str  # text of every <pre> and <code> element, one per line
    has_code_block: bool  # at least one <pre> block (inline <code> alone does not count)
    has_link: bool  # at least one <a href=...>


def collapse(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def split_body(html: str) -> BodyParts:
    """Separates a question body into prose and code. Shared by the text and the context features."""
    soup = BeautifulSoup(html or "", "html.parser")
    has_code_block = soup.find("pre") is not None
    has_link = soup.find("a", href=True) is not None
    code_parts: list[str] = []
    # <pre> first (it usually wraps a <code>), then any inline <code> left over.
    for name in ("pre", "code"):
        for element in soup.find_all(name):
            code_parts.append(element.get_text())
            element.decompose()
    # A space separator keeps words from neighbouring tags apart ("<p>a</p><p>b</p>" -> "a b").
    prose = collapse(soup.get_text(" "))
    return BodyParts(
        prose=prose, code="\n".join(code_parts), has_code_block=has_code_block, has_link=has_link
    )


def first_words(text: str, n: int) -> str:
    return " ".join(text.split()[:n])


def build_text(title: str, body_html: str, body_prose_words: int = 64) -> str:
    """The exact string the model sees: title, then up to `body_prose_words` words of prose."""
    prose = first_words(split_body(body_html).prose, body_prose_words)
    return collapse(f"{title or ''} {prose}")
