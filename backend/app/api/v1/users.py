"""
users.py
========
WHAT THIS FILE DOES
-------------------
Endpoints about the user themselves.

    GET /users/me    who am I?

WHY A "WHO AM I" ENDPOINT EXISTS AT ALL
---------------------------------------
The frontend stores only a JWT. The token's payload does technically contain
the user id and role, but the frontend must never TRUST what it reads there:
the payload is merely base64-encoded, so anyone can edit it in their browser.
Only the server can verify the signature.

So the frontend asks the server. This endpoint returns the authoritative
answer, which is what the UI uses to display the signed-in email, and to decide
whether to show Admin-only controls.

It also doubles as a token check: a 200 means the token is still valid, a 401
means it is time to sign in again.
"""

from fastapi import APIRouter, Depends

from app.api import deps
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def read_user_me(
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Return the currently authenticated user's profile.

    There is no database query in the body, because the dependency has already
    done all the work: it decoded and verified the token, loaded the user, and
    confirmed the account is active. All that remains is to return the object.

    `response_model=UserOut` is doing something important here. `current_user`
    is a full `User` row and DOES carry `hashed_password`, but `UserOut` does
    not declare that field, so Pydantic drops it. The hash cannot leak, because
    exposing it would require deliberately adding it to the schema.
    """
    return current_user
