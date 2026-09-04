"""
user.py  (schemas)
==================
WHAT THIS FILE DOES
-------------------
Describes the SHAPE of user data going into and out of the API.

THE MOST IMPORTANT THING ON THIS PAGE
-------------------------------------
Look at `UserOut` below and notice what is NOT there: `hashed_password`.

Pydantic returns ONLY the fields a schema declares. Even though the `User`
object handed to it carries the password hash, that field is silently dropped
because the schema does not mention it.

That is a genuine security control, not a formatting nicety. Any endpoint
returning `response_model=UserOut` is structurally incapable of leaking the
hash -- there is no way to forget, because omission is the default.

WHY SEPARATE "IN" AND "OUT" SCHEMAS?
------------------------------------
The fields a client may SEND are not the fields we are willing to RETURN.

    UserCreate  takes a plain `password`  (in, never stored as given)
    UserOut     returns `id`, `is_active` (out, never accepted from a client)

If one schema did both, a client could POST `{"is_active": true, "role":
"Admin"}` and promote themselves. Splitting them makes that impossible.
"""

import datetime
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    """Fields shared by several user schemas, defined once."""

    # `EmailStr` validates the address format automatically. A malformed email
    # is rejected with a clear 422 before any of our code runs.
    email: EmailStr

    # `Literal` restricts the value to exactly these three strings. Anything
    # else is rejected, so an invalid role can never reach the database.
    role: Literal["Admin", "Manager", "Employee"] = "Employee"


class UserCreate(UserBase):
    """
    Body for POST /auth/signup.

    A new user either CREATES an organization or JOINS one, which is why both
    org fields are optional -- exactly one should be supplied. The endpoint
    enforces that, since Pydantic alone cannot express "one or the other".
    """

    # The PLAIN password. It arrives here, is immediately bcrypt-hashed by
    # core/security.py, and the plain value is never stored or logged.
    password: str

    # Supply this to create a brand-new tenant. The signup endpoint then makes
    # you its Admin, regardless of the `role` field above.
    org_name: Optional[str] = None

    # Supply this instead to join an EXISTING organization, in which case the
    # `role` field is honoured.
    org_id: Optional[uuid.UUID] = None


class UserUpdate(BaseModel):
    """
    Body for editing a user. Every field is optional so a caller can send just
    the one they want to change (a PATCH-style partial update) rather than
    having to resend the whole object.

    Note it does NOT inherit from UserBase: inheriting would make `email`
    required, which defeats the purpose of a partial update.
    """

    email: Optional[EmailStr] = None
    role: Optional[Literal["Admin", "Manager", "Employee"]] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserOut(UserBase):
    """
    What the API returns about a user.

    Contains no password field of any kind -- see the module docstring.
    """

    # `from_attributes=True` lets Pydantic build this straight from a
    # SQLAlchemy row by reading its attributes. Without it, every endpoint
    # would have to copy each field across by hand.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
