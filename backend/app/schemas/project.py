"""
project.py  (schemas)
=====================
Describes the shape of project data crossing the API boundary.

A project is a document collection AND a search boundary -- a question asked
inside one project never retrieves chunks from another. See models/project.py.

THE PATTERN USED THROUGHOUT THIS PROJECT
----------------------------------------
    ...Base    fields common to several schemas, written once
    ...Create  what a client may SEND when creating
    ...Update  what a client may SEND when editing
    ...Out     what the API RETURNS

Splitting create from out is what stops a client inventing server-controlled
values. Notice `ProjectCreate` accepts only a name: `id`, `org_id` and the
timestamps are all decided by the server. A client cannot post an `org_id` and
plant a project inside somebody else's organization, because the field is not
part of the schema at all -- the endpoint takes it from the caller's verified
JWT instead.
"""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class ProjectBase(BaseModel):
    """The one field a human actually chooses."""

    name: str


class ProjectCreate(ProjectBase):
    """
    Body for POST /projects/.

    Empty because it needs nothing beyond the inherited `name`. It exists as a
    distinct class anyway, so that creation-only fields can be added later
    without touching the response shape -- and so the generated API docs name
    the request body meaningfully.
    """

    pass


class ProjectUpdate(ProjectBase):
    """Body for renaming a project."""

    pass


class ProjectOut(ProjectBase):
    """A project as returned by the API."""

    # Build directly from the SQLAlchemy row by reading its attributes.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    # Returned so a client can confirm which tenant owns the project. Safe to
    # expose, because a user only ever receives projects from their OWN
    # organization -- the endpoint filters on `current_user.org_id`.
    org_id: uuid.UUID

    created_at: datetime.datetime
    updated_at: datetime.datetime
