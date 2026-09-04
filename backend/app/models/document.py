"""
document.py
===========
WHAT THIS FILE DOES
-------------------
Defines the DOCUMENT table -- the record of one uploaded file.

Note the distinction: this row is the RECORD, not the file. The bytes live on
disk at `file_path`; this table stores everything we know ABOUT them.

THE STATUS FIELD IS THE HEART OF THIS TABLE
-------------------------------------------
Because processing happens in a background worker, the browser has no way of
being told when it finishes. This column is how progress is communicated:

    pending     uploaded, sitting in the Celery queue
    processing  a worker has picked it up
    completed   chunked, embedded and SEARCHABLE
    failed      something went wrong; the reason is in meta_data["error"]

The frontend polls until it reads "completed", and services/retrieval.py
searches ONLY completed documents -- a half-processed file would otherwise
return partial answers that look complete.

TWO FEATURES WORTH UNDERSTANDING
--------------------------------
DEDUPLICATION. Every upload is SHA-256 hashed. Uploading the same file twice
into one project is detected and skipped, saving the expensive OCR and
embedding work. A SHA-256 of the CONTENT means a renamed file is still caught.

VERSIONING. Uploading a file with a name already present in the project stores
it as version 2, 3 and so on, rather than overwriting. Document history is
preserved.
"""

import datetime
import uuid
from typing import List, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.chunk import Chunk
    from app.models.project import Project


class Document(Base):
    """One uploaded file. Table name: "documents"."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # The name the user uploaded, shown in the UI and in citations.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    # The extension without the dot: "pdf", "docx", "xlsx". This is what
    # extractor.py dispatches on to choose a parser.
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Size in bytes. Displayed as KB/MB by the frontend.
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    # Where the bytes actually live. Stored under a uuid-prefixed name so two
    # users uploading "report.pdf" cannot overwrite each other on disk.
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    # pending | processing | completed | failed  -- see the docstring above.
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )

    # SHA-256 of the file's CONTENTS, used for deduplication.
    #
    # `index=True` but NOT unique here. Uniqueness is enforced on the PAIR
    # (project_id, duplicate_hash) by a migration, because the same file may
    # legitimately exist in two different projects -- and a globally unique
    # constraint would let one tenant's upload block another's.
    duplicate_hash: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )

    # Revision number for repeated uploads of the same filename.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # ---- The flexible metadata column ----
    # JSONB is Postgres's binary JSON type: queryable and indexable, unlike a
    # plain text column holding JSON.
    #
    # This is where the ingestion pipeline records everything it learned:
    #   language, word_count, char_count, page_count
    #   chunk_count, chunk_strategy, chunk_size, chunk_overlap
    #   embedding_model, embedding_provider, embedding_dimension
    #   needs_ocr, ocr_applied, processing_seconds
    #   error            (only when status == "failed")
    #
    # Using JSONB means adding a new metadata field later needs NO migration --
    # which matters because the pipeline gains new measurements over time.
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- Relationships -------------------------------------------------
    project: Mapped["Project"] = relationship("Project", back_populates="documents")

    # Deleting a document deletes its chunks, and their cascade in turn removes
    # the embeddings. That chain is what keeps the vector index free of rows
    # pointing at documents that no longer exist.
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )
