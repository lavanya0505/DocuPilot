"""
organization.py  (schemas)
==========================
Describes the shape of organization data crossing the API boundary.

An organization is a TENANT -- one company using the platform. It is the root
of the ownership chain that makes data isolation possible:

    Organization -> Project -> Document -> Chunk -> ChunkEmbedding

See models/organization.py for the full picture.

HOW ORGANIZATIONS ARE ACTUALLY CREATED
--------------------------------------
There is no "create organization" endpoint. One is created implicitly during
signup, when a user supplies `org_name` -- and that first user becomes its
Admin. See api/v1/auth.py.

These schemas therefore exist mainly for reading, and as the vocabulary for
organization-management endpoints that a future admin panel would need.
"""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class OrganizationBase(BaseModel):
    """The company name."""

    name: str


class OrganizationCreate(OrganizationBase):
    """
    Body for creating an organization directly.

    Currently unused, since organizations are created through signup, but kept
    so the schema layer stays symmetrical with the other resources and an admin
    endpoint can be added without inventing new vocabulary.
    """

    pass


class OrganizationUpdate(OrganizationBase):
    """Body for renaming an organization."""

    pass


class OrganizationOut(OrganizationBase):
    """
    An organization as returned by the API.

    Deliberately minimal. It exposes no counts of users, projects or documents:
    that information is only meaningful to someone inside the tenant, and each
    extra field is one more thing to reason about when checking that nothing
    leaks across tenant boundaries.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
