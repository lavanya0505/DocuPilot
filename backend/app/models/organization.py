"""
organization.py
===============
WHAT THIS FILE DOES
-------------------
Defines the ORGANIZATION table -- the root of the whole multi-tenant design.

WHAT "MULTI-TENANT" MEANS
-------------------------
One running application serves many separate companies ("tenants") out of one
database, and none of them can see any other's data.

Everything hangs off this table:

        Organization  (a company)
             |
             +-- Users        who can log in
             +-- Projects     document collections
             |      |
             |      +-- Documents
             |             |
             |             +-- Chunks -> ChunkEmbeddings   <- what search reads
             |
             +-- APIKeys      programmatic access
             +-- AuditLogs    who did what

WHY THIS SHAPE MATTERS FOR SECURITY
-----------------------------------
Because every piece of data traces back to exactly one organization, a search
can join up that chain and filter on the caller's own `org_id`. See the query
in services/retrieval.py: the tenant boundary is enforced inside the SQL
itself, not by application code that a developer might forget to write.

An organization is created automatically when the first user signs up with an
`org_name`, and that user becomes its Admin.
"""

import datetime
import uuid
from typing import List, TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

# Imported only for the type checker. A real import would be circular, since
# every one of these modules imports something that leads back here.
if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.audit import AuditLog
    from app.models.project import Project
    from app.models.user import User


class Organization(Base):
    """A tenant. Table name is generated automatically as "organizations"."""

    # A UUID rather than an auto-incrementing integer, for two reasons:
    #   * ids stay unique if data is ever merged across databases,
    #   * ids are unguessable, so nobody can enumerate /organizations/1, /2, /3.
    # `default=uuid.uuid4` passes the FUNCTION itself. Writing `uuid.uuid4()`
    # would call it once at import time and give every row the same id.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # `server_default=func.now()` means POSTGRES sets the timestamp, not Python.
    # The database clock is the single source of truth, so app servers in
    # different time zones cannot disagree about when something happened.
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # `onupdate` refreshes this automatically on every change to the row.
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- Relationships -------------------------------------------------
    # Not columns. They let you navigate between objects in Python:
    # `organization.users` returns the list, `user.organization` goes back.
    #
    # `cascade="all, delete-orphan"` means deleting an organization deletes
    # everything belonging to it. That is the correct behaviour for a tenant
    # root: no orphaned company data should survive.
    users: Mapped[List["User"]] = relationship(
        "User", back_populates="organization", cascade="all, delete-orphan"
    )
    projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="organization", cascade="all, delete-orphan"
    )
    api_keys: Mapped[List["APIKey"]] = relationship(
        "APIKey", back_populates="organization", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="organization", cascade="all, delete-orphan"
    )
