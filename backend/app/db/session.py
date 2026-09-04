"""
session.py
==========
WHAT THIS FILE DOES
-------------------
Creates the connection to PostgreSQL, and hands out "sessions" -- the objects
that every other part of the app uses to read and write the database.

THREE THINGS LIVE HERE
----------------------
    engine        the connection factory. One per process.
    SessionLocal  makes new sessions from the engine.
    get_db()      a FastAPI dependency that opens a session per request.

WHAT IS A SESSION?
------------------
A workspace for one unit of work. You add objects to it, change them, and then
`commit()` to write everything at once -- or `rollback()` to discard the lot.

Crucially it is a TRANSACTION boundary. In the ingestion pipeline, chunks,
embeddings and the document's status change are all committed together, so
there is no possible state where chunks exist but the document still says
"processing".

WHY "ASYNC"?
------------
A database query spends almost all of its time WAITING for Postgres to answer.
A synchronous server sits idle during that wait. An async one uses the time to
serve other requests instead, so a single process can handle far more users.
That is what the `asyncpg` driver and the `await` keywords buy us.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# ----------------------------------------------------------------------
# THE ENGINE
# ----------------------------------------------------------------------
# The engine holds the connection configuration and manages actual TCP
# connections to Postgres. It is created ONCE when this module is first
# imported, and shared by everything in the process.
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    # Print every SQL statement while developing. Invaluable for seeing exactly
    # what SQLAlchemy generated -- and far too noisy and slow for production,
    # which is why it is tied to the environment.
    echo=settings.ENV == "development",
    future=True,
    # ---- WHY NullPool, AND NOT THE DEFAULT POOL ----
    # Normally you WANT a connection pool: opening a database connection is
    # expensive, so keeping a handful open and reusing them is much faster.
    #
    # But Celery breaks that assumption. Celery tasks are synchronous, so each
    # one calls `asyncio.run()`, which creates a brand-new event loop and then
    # destroys it when the task finishes.
    #
    # A pooled connection created inside loop #1 and reused inside loop #2
    # raises "Event loop is closed", because the connection's internals are
    # bound to the loop that made them.
    #
    # NullPool disables pooling: every session opens a fresh connection and
    # closes it afterwards. Slightly slower, but correct in both the web
    # process and the worker -- and correctness wins.
    poolclass=NullPool,
)

# ----------------------------------------------------------------------
# THE SESSION FACTORY
# ----------------------------------------------------------------------
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # ---- WHY expire_on_commit=False ----
    # By default SQLAlchemy marks every object as "stale" after a commit, so
    # touching any attribute triggers a fresh SELECT to reload it.
    #
    # In async code that lazy reload happens implicitly and can fire at an
    # awkward moment -- including after the session has closed, which raises a
    # confusing MissingGreenlet error. Setting this False keeps the objects
    # usable after commit, which is exactly what endpoints need when they
    # return a freshly created row.
    expire_on_commit=False,
    # We commit explicitly, so that a failure part way through leaves nothing
    # half-written.
    autocommit=False,
    # Do not silently flush pending changes before every query. Explicit
    # `flush()` calls make the ordering of writes obvious.
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session to a FastAPI endpoint, then clean it up.

    Used as `db: AsyncSession = Depends(get_db)` in an endpoint signature.

    HOW THE `yield` WORKS HERE
    --------------------------
    This is a generator dependency. FastAPI runs the code up to `yield`, hands
    the session to the endpoint, and then -- once the response has been sent --
    resumes this function to run the cleanup.

    That guarantees the connection is released even if the endpoint raises,
    which is what stops a busy API slowly exhausting the database's connection
    limit.
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
