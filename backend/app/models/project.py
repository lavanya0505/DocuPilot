"""
project.py
==========
WHAT THIS FILE DOES
-------------------
Defines the PROJECT table -- a folder of related documents.

WHY PROJECTS EXIST, AND WHY THEY ARE MORE THAN FOLDERS
------------------------------------------------------
A project is a SEARCH BOUNDARY, not just an organisational convenience.

A question asked inside "HR Policies" only ever retrieves chunks from documents
uploaded to "HR Policies". That has two real benefits:

  * RELEVANCE. Someone asking about payroll will never be answered with a
    paragraph from an engineering runbook that happened to use similar wording.

  * SPEED. Filtering by project before the vector comparison means Postgres has
    far fewer rows to consider.

WHERE IT SITS
-------------
        Organization -> Project -> Document -> Chunk -> ChunkEmbedding

`org_id` here is the link that makes tenant isolation enforceable: the search
query joins Chunk all the way up to Project and filters on THIS column. Without
a project's organization being recorded, there would be no way to tell whose
documents a chunk belongs to.
"""

import datetime
import uuid
from typing import List, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.chat import ChatSession
    from app.models.document import Document
    from app.models.organization import Organization


class Project(Base):
    """A document collection and search boundary. Table name: "projects"."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # e.g. "HR Policies", "Q3 Contracts", "Engineering Runbooks".
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Which organization owns this project.
    #
    # `ondelete="CASCADE"` means Postgres itself deletes this row if the
    # organization is deleted. The guarantee lives in the DATABASE, so orphaned
    # projects cannot survive even a bug in the application layer.
    #
    # This column is what services/retrieval.py filters on to enforce tenancy.
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- Relationships -------------------------------------------------
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="projects"
    )

    # Deleting a project removes its documents, and through their own cascades
    # the chunks and embeddings too -- so no unreachable vectors are left behind
    # taking up space in the index.
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan"
    )

    # Conversations are scoped to a project, which is how a follow-up question
    # stays anchored to the same set of documents.
    chat_sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession", back_populates="project", cascade="all, delete-orphan"
    )
