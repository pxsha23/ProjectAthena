"""Zip export of a project's files."""

import io
import re
import zipfile
from collections.abc import Iterable

from app.models import ProjectFile


def safe_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def build_zip(files: Iterable[ProjectFile], root: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for f in files:
            archive.writestr(f"{root}/{f.path}", f.content)
    return buffer.getvalue()
