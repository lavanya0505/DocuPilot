"""
chunk.py  (database models)
===========================
WHAT THIS FILE DOES
-------------------
Defines the two database tables at the heart of semantic search:

    Chunk           -- a piece of a document, as readable TEXT
    ChunkEmbedding  -- that same piece, as a VECTOR of numbers

WHY SPLIT A DOCUMENT INTO CHUNKS AT ALL?
----------------------------------------
Two reasons, and both are fundamental to how RAG works.

  1. LLMs have a size limit. You cannot paste a 300-page manual into a prompt.

  2. More importantly, PRECISION. If you embedded an entire book as one
     vector, that vector would represent "a book about many things" and would
     be a weak match for any specific question. A single paragraph embeds to a
     vector representing one clear idea, which matches sharply. Retrieval also
     becomes far more useful: instead of "the answer is somewhere in this
     300-page file", you get "the answer is this paragraph, on page 12".

WHY ARE TEXT AND VECTOR IN SEPARATE TABLES?
-------------------------------------------
This is a deliberate design choice, not an accident:

  * You can store SEVERAL vectors for one chunk -- one per embedding model.
    That is what makes it possible to migrate from a 384-dimension local model
    to a 1536-dimension OpenAI model without deleting anything, and to compare
    the two side by side.

  * Reading chunk text (to display it to the user) does not drag the heavy
    vector data along with it. A 384-float vector is around 1.5 KB, so this
    materially speeds up ordinary listing queries.

WHAT IS SQLALCHEMY DOING HERE?
------------------------------
SQLAlchemy is an ORM -- Object Relational Mapper. It lets us describe tables as
Python classes, then write Python instead of raw SQL:

        chunk = Chunk(content="...", page_number=3)
        db.add(chunk)

instead of hand-writing INSERT statements. It also protects against SQL
injection automatically, because values are always sent as bound parameters
rather than pasted into the query text.
"""

import datetime
import uuid
from typing import List, TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.config import settings
from app.db.base_class import Base

# `TYPE_CHECKING` is False at runtime and True while a type checker is reading
# the file. Importing Document here would create a circular import (document.py
# imports chunk.py and vice versa), so we import it only for the type checker
# and write the annotation as a string, "Document", below.
if TYPE_CHECKING:
    from app.models.document import Document


class Chunk(Base):
    """
    One piece of a document, stored as readable text.

    The table name is generated automatically as "chunks" -- see
    db/base_class.py, which converts the class name to snake_case and
    pluralises it.
    """

    # The primary key. A UUID rather than an auto-incrementing integer because:
    #   * ids stay unique even if data is merged across databases,
    #   * ids are unguessable, so nobody can enumerate /documents/1, /2, /3...
    # `default=uuid.uuid4` passes the FUNCTION, not a call to it, so a NEW id
    # is generated for each row. Writing `uuid.uuid4()` here would compute one
    # id at import time and reuse it forever.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Which document this chunk came from.
    # `ondelete="CASCADE"` means: if that document is deleted, Postgres itself
    # deletes this row too. The guarantee lives in the database, so orphaned
    # chunks cannot survive even a bug in the application code.
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    # The actual text. `Text` rather than `String(n)` because chunks have no
    # fixed maximum length.
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Position within the document: 0, 1, 2... Used to reassemble chunks in
    # order, and to show neighbouring context around a search hit.
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Which page this text appeared on. Nullable because plenty of formats
    # genuinely have no pages -- a CSV, an email, an HTML file. This single
    # column is what makes citations say "page 12" instead of just naming a file.
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)

    # Flexible extra facts about the chunk, stored as JSONB (Postgres's binary,
    # indexable JSON type). Holds token_count, character_count, and for
    # markdown-chunked documents the header_section this text sits under.
    # Using JSONB means adding a new metadata field later needs no migration.
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # `server_default=func.now()` means POSTGRES fills in the timestamp, not
    # Python. That matters because the database clock is the single source of
    # truth -- app servers in different time zones cannot disagree.
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ---- Relationships -------------------------------------------------
    # These are not columns. They tell SQLAlchemy how to navigate between
    # objects in Python: `chunk.document` fetches the parent Document, and
    # `document.chunks` lists all its chunks.
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    # `cascade="all, delete-orphan"` is the Python-side mirror of the database
    # ON DELETE CASCADE above: deleting a Chunk through SQLAlchemy also deletes
    # its embeddings.
    embeddings: Mapped[List["ChunkEmbedding"]] = relationship(
        "ChunkEmbedding", back_populates="chunk", cascade="all, delete-orphan"
    )

    # `__table_args__` holds table-level options such as indexes.
    __table_args__ = (
        # A composite index on (document_id, chunk_index). Without it, fetching
        # one document's chunks in order forces Postgres to scan the entire
        # chunks table. With it, the lookup goes straight to the right rows.
        Index("ix_chunks_document_order", "document_id", "chunk_index"),
    )


class ChunkEmbedding(Base):
    """
    The vector representation of one chunk -- its meaning, expressed as numbers.

    THIS TABLE IS WHAT MAKES SEMANTIC SEARCH POSSIBLE.

    When a user asks a question, we convert the question into a vector and ask
    Postgres which rows in THIS table point in the most similar direction. See
    services/retrieval.py for that query.
    """

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )

    # >>> THE VECTOR COLUMN -- the single most important line in this file <<<
    #
    # `Vector` comes from the pgvector extension, which teaches Postgres a
    # native vector type along with distance operators (`<=>` for cosine
    # distance) and specialised indexes.
    #
    # The dimension MUST be fixed and MUST match the embedding model exactly:
    #     all-MiniLM-L6-v2       -> 384   (our default, free and local)
    #     text-embedding-3-small -> 1536  (OpenAI)
    #
    # Declaring the size matters for two reasons:
    #   1. Postgres rejects a wrong-sized vector immediately, rather than
    #      silently corrupting the search results.
    #   2. You cannot build a vector INDEX on a dimensionless column. Without
    #      an index, every search reads every row -- fine for 100 documents,
    #      unusable at 100,000.
    embedding: Mapped[List[float]] = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION), nullable=False
    )

    # WHICH model produced this vector, e.g. "all-MiniLM-L6-v2".
    # Vectors from different models are not comparable at all, so this column
    # is what lets you identify stale rows after a model change instead of
    # silently returning meaningless results.
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunk: Mapped["Chunk"] = relationship("Chunk", back_populates="embeddings")

    __table_args__ = (
        # THE VECTOR INDEX -- what keeps search fast as data grows.
        #
        # HNSW ("Hierarchical Navigable Small World") builds a graph of vectors
        # so a search can hop towards the nearest neighbours instead of
        # comparing against every row. It is an APPROXIMATE index: it may very
        # occasionally miss a true nearest neighbour, in exchange for being
        # orders of magnitude faster. For document search that trade is
        # overwhelmingly worth it.
        #
        # `vector_cosine_ops` tells the index to optimise for COSINE distance,
        # which must match the operator used in the query. An index built for a
        # different distance function is simply ignored by the planner.
        #
        # m = how many links each node keeps in the graph (higher = more
        #     accurate, larger index)
        # ef_construction = how hard the build works to place each node
        #     (higher = better quality index, slower to build)
        Index(
            "ix_chunk_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
