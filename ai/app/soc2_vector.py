"""
pgvector-backed document chunking and semantic search for SOC-2 reports (#13).

Flow:
1. During extraction, chunk document text into ~500-token segments (50-token overlap)
2. Embed each chunk with text-embedding-3-small ($0.02/1M tokens)
3. Store in document_chunks table with source_id, page_number, chunk_type
4. Query: embed question -> cosine similarity search -> return top-k chunks
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import psycopg2
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIM = 1536
_CHUNK_SIZE_CHARS = 2000  # ~500 tokens
_CHUNK_OVERLAP_CHARS = 200  # ~50 tokens


def _get_dsn() -> str:
    return (
        f"host={os.environ.get('PGHOST', 'localhost')} "
        f"port={os.environ.get('PGPORT', '5432')} "
        f"dbname={os.environ.get('PGDATABASE', 'solon')} "
        f"user={os.environ.get('PGUSER', 'solon')} "
        f"password={os.environ.get('PGPASSWORD', 'solon_dev')}"
    )


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI()


# ═══════════════════════════════════════════════════════════════════════
# Chunking
# ═══════════════════════════════════════════════════════════════════════


def chunk_document(
    classified_pages: list[dict],
) -> list[dict]:
    """Split classified pages into overlapping text chunks.

    Each chunk dict: {text, page_number, chunk_type, chunk_index}
    """
    chunks: list[dict] = []
    chunk_idx = 0

    for page in classified_pages:
        text = page.get("text", "").strip()
        if not text:
            continue

        page_num = page["page"]
        chunk_type = page.get("type", "narrative")

        pos = 0
        while pos < len(text):
            end = pos + _CHUNK_SIZE_CHARS
            chunk_text = text[pos:end]

            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "page_number": page_num,
                    "chunk_type": chunk_type,
                    "chunk_index": chunk_idx,
                })
                chunk_idx += 1

            pos += _CHUNK_SIZE_CHARS - _CHUNK_OVERLAP_CHARS

    return chunks


# ═══════════════════════════════════════════════════════════════════════
# Embedding
# ═══════════════════════════════════════════════════════════════════════


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using text-embedding-3-small."""
    if not texts:
        return []

    oai = _get_client()
    resp = await oai.embeddings.create(model=_EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in resp.data]


# ═══════════════════════════════════════════════════════════════════════
# Store chunks with embeddings
# ═══════════════════════════════════════════════════════════════════════


async def store_chunks(
    source_id: str,
    classified_pages: list[dict],
) -> int:
    """Chunk a document, embed, and store in document_chunks.

    Returns the number of chunks stored.
    """
    chunks = chunk_document(classified_pages)
    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]

    # Batch embed (API supports up to 2048 inputs)
    batch_size = 100
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embeddings = await embed_texts(batch)
        all_embeddings.extend(embeddings)

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            for chunk, embedding in zip(chunks, all_embeddings):
                cur.execute(
                    """INSERT INTO document_chunks
                           (id, source_id, page_number, chunk_index, content,
                            chunk_type, embedding)
                       VALUES (%s, %s::uuid, %s, %s, %s, %s, %s::vector)""",
                    (
                        str(uuid.uuid4()),
                        source_id,
                        chunk["page_number"],
                        chunk["chunk_index"],
                        chunk["text"],
                        chunk["chunk_type"],
                        json.dumps(embedding),
                    ),
                )
        conn.commit()
        logger.info("Stored %d chunks for source %s", len(chunks), source_id)
    finally:
        conn.close()

    return len(chunks)


# ═══════════════════════════════════════════════════════════════════════
# Semantic query
# ═══════════════════════════════════════════════════════════════════════


async def query_soc2_document(
    source_id: str,
    question: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Embed the question, query pgvector for cosine similarity, return top-k chunks."""
    embeddings = await embed_texts([question])
    if not embeddings:
        return []

    query_vec = json.dumps(embeddings[0])

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT content, page_number, chunk_type,
                          1 - (embedding <=> %s::vector) AS similarity
                   FROM document_chunks
                   WHERE source_id = %s::uuid
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s""",
                (query_vec, source_id, query_vec, top_k),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "text": row[0],
            "page_number": row[1],
            "chunk_type": row[2],
            "similarity": round(float(row[3]), 4),
        }
        for row in rows
    ]
