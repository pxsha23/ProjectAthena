"""Semantic code search: chunk project files, embed them, store in pgvector, query by similarity."""

import asyncio
import hashlib
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from sqlalchemy import Float, bindparam, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import CodeChunk, ProjectFile

CHUNK_LINES = 40
CHUNK_OVERLAP = 8


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Dependency-free embedder (hashed bag of tokens). Good enough for tests and offline development."""

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", text.lower()):
                bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim
                vec[bucket] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, dim: int) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                'sentence-transformers is not installed. Run: uv pip install -e ".[embeddings]" '
                "or set EMBEDDINGS_BACKEND=hash"
            ) from exc
        self._model = SentenceTransformer(model_name)
        self.dim = dim
        actual = self._model.get_sentence_embedding_dimension()
        if actual != dim:
            raise RuntimeError(f"{model_name} produces {actual}-dim vectors but EMBEDDING_DIM={dim}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embeddings_backend == "hash":
        return HashEmbedder(settings.embedding_dim)
    if not settings.embeddings_model:
        raise RuntimeError("Set EMBEDDINGS_MODEL (for example sentence-transformers/all-MiniLM-L6-v2)")
    return SentenceTransformerEmbedder(settings.embeddings_model, settings.embedding_dim)


@dataclass
class Chunk:
    file_path: str
    start_line: int
    end_line: int
    content: str


def chunk_file(path: str, content: str) -> list[Chunk]:
    lines = content.splitlines()
    if not lines:
        return []
    chunks, start = [], 0
    while start < len(lines):
        end = min(len(lines), start + CHUNK_LINES)
        chunks.append(Chunk(path, start + 1, end, "\n".join(lines[start:end])))
        if end == len(lines):
            break
        start = end - CHUNK_OVERLAP
    return chunks


async def index_project(session: AsyncSession, project_id: str, files: list[ProjectFile]) -> int:
    chunks = [c for f in files for c in chunk_file(f.path, f.content)]
    await session.execute(delete(CodeChunk).where(CodeChunk.project_id == project_id))
    if chunks:
        # Include the path in the embedded text so searches like "login route" can match file names.
        # Embedding is CPU-bound; run it off the event loop.
        texts = [f"{c.file_path}\n{c.content}" for c in chunks]
        vectors = await asyncio.to_thread(get_embedder().embed, texts)
        session.add_all(
            CodeChunk(
                project_id=project_id,
                file_path=c.file_path,
                start_line=c.start_line,
                end_line=c.end_line,
                content=c.content,
                embedding=v,
            )
            for c, v in zip(chunks, vectors, strict=True)
        )
    await session.commit()
    return len(chunks)


@dataclass
class SearchHit:
    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float


async def search(session: AsyncSession, project_id: str, query: str, limit: int = 8) -> list[SearchHit]:
    [vector] = await asyncio.to_thread(get_embedder().embed, [query])
    if session.bind.dialect.name == "postgresql":
        # pgvector cosine distance operator; the bind param reuses the column type so it is sent as a vector.
        query_vector = bindparam("query_vector", vector, type_=CodeChunk.embedding.type)
        distance = CodeChunk.embedding.op("<=>", return_type=Float())(query_vector)
        rows = await session.execute(
            select(CodeChunk, distance.label("distance"))
            .where(CodeChunk.project_id == project_id)
            .order_by(distance)
            .limit(limit)
        )
        return [
            SearchHit(c.file_path, c.start_line, c.end_line, c.content, round(1 - float(d), 4))
            for c, d in rows
        ]

    # Fallback for SQLite (tests): cosine similarity in Python. Vectors are already normalized.
    chunks = (await session.scalars(select(CodeChunk).where(CodeChunk.project_id == project_id))).all()
    scored = sorted(
        ((sum(a * b for a, b in zip(vector, c.embedding, strict=True)), c) for c in chunks),
        key=lambda pair: pair[0],
        reverse=True,
    )[:limit]
    return [SearchHit(c.file_path, c.start_line, c.end_line, c.content, round(s, 4)) for s, c in scored]
