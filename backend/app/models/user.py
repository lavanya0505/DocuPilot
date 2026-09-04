"""
user.py
=======
WHAT THIS FILE DOES
-------------------
Defines the USER table -- someone who can log in.

Every user belongs to exactly one Organization. That single `org_id` column is
what the whole tenant isolation rests on: it is the value compared against in
every search query in services/retrieval.py.

THE THREE ROLES
---------------
    Admin     created the organization. Full control.
    Manager   can create projects and upload documents.
    Employee  can read, search and ask questions.

Roles are checked by `RoleChecker` in api/deps.py, for example:

        Depends(deps.RoleChecker(["Admin", "Manager"]))

A NOTE ON THE PASSWORD COLUMN
-----------------------------
The column is `hashed_password`, and the naming is deliberate. The plain
password is never stored, never logged and never returned by the API. Only a
bcrypt hash -- a one-way fingerprint -- is kept. See core/security.py.

The API can never leak it either: the `UserOut` schema in schemas/user.py does
not list the field, and Pydantic returns only the fields it declares.
"""

import datetime
import uuid
from typing import List, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.audit import AuditLog
    from app.models.chat import ChatSession
    from app.models.organization import Organization


class User(Base):
    """A person who can sign in. Table name: "users"."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # `unique=True` is enforced by the DATABASE, not just by the signup check.
    # That distinction matters: two signup requests arriving at the same instant
    # could both pass an application-level "does this email exist?" test, and
    # only the database constraint reliably stops the duplicate.
    #
    # `index=True` because every login looks a user up by email, and without an
    # index that means scanning the entire table.
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    # The bcrypt hash. 255 characters is ample -- bcrypt hashes are 60.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Admin | Manager | Employee. Stored as a string rather than a database
    # ENUM because adding a new role to an ENUM requires a migration, whereas
    # this only needs a code change. The allowed values are enforced by the
    # Pydantic schema on the way in.
    role: Mapped[str] = mapped_column(
        String(50), default="Employee", nullable=False
    )

    # >>> THE TENANT BOUNDARY <<<
    # This column is copied into the user's JWT at login and then compared
    # against `projects.org_id` in every retrieval query. It is the single most
    # security-critical field in the schema.
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Lets an account be disabled without deleting it -- which preserves their
    # audit history and authorship. Checked by `get_current_active_user`, so
    # deactivation takes effect immediately even while their token is still
    # within its lifetime.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Groundwork for email verification. Not enforced yet.
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- Relationships -------------------------------------------------
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="users"
    )
    api_keys: Mapped[List["APIKey"]] = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession", back_populates="user", cascade="all, delete-orphan"
    )
