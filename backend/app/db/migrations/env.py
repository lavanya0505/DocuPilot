"""
env.py  (Alembic environment)
=============================
WHAT THIS FILE DOES
-------------------
This is the script Alembic runs every time you type a migration command:

        alembic upgrade head          apply pending migrations
        alembic revision --autogenerate -m "..."   write a new one
        alembic downgrade -1          undo the last one

Its job is to set three things up before any migration runs:

    1. Make `app.*` importable, so our models can be found.
    2. Point Alembic at the right database.
    3. Hand Alembic the model metadata, so autogenerate can compare the code
       against the real schema.

TWO THINGS HERE ARE SPECIFIC TO THIS PROJECT
--------------------------------------------
  * It uses the SYNCHRONOUS database URL. Alembic is not async, so it cannot
    use the asyncpg driver the application runs on. `SQLALCHEMY_SYNC_DATABASE_URI`
    in core/config.py exists purely to serve this file.

  * It enables the pgvector extension before running anything. Without that,
    the very first migration would fail at the point it tries to create a
    `vector` column, because Postgres would not know what a vector is.

OFFLINE VERSUS ONLINE MODE
--------------------------
    online   the normal case. Connects to the database and applies changes.
    offline  connects to nothing and PRINTS the SQL instead, so a DBA can
             review it and run it by hand. Common where production databases
             are locked down and applications may not alter schemas directly.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# ----------------------------------------------------------------------
# 1. MAKE THE APPLICATION IMPORTABLE
# ----------------------------------------------------------------------
# Alembic runs this file directly, so `backend/` is not automatically on the
# Python path and `from app.models import Base` below would fail.
#
# Walk up three levels to reach `backend/`:
#   __file__   -> backend/app/db/migrations/env.py
#   dirname x1 -> backend/app/db/migrations
#   .. x3      -> backend
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
)

# The Alembic Config object, giving access to everything in alembic.ini.
config = context.config

# Set up Python logging from alembic.ini, so migration progress is printed.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Imported AFTER the sys.path change above -- these lines would raise
# ModuleNotFoundError if placed at the top of the file with the other imports.
from app.core.config import settings  # noqa: E402
from app.models import Base  # noqa: E402

# ----------------------------------------------------------------------
# 2. POINT ALEMBIC AT THE DATABASE
# ----------------------------------------------------------------------
# Overriding the URL here rather than hard-coding it in alembic.ini means the
# same command works on your laptop and on Render, driven entirely by
# environment variables. It also keeps the database password out of a file that
# is committed to git.
#
# Note this is the SYNC URI: Alembic cannot drive the async asyncpg driver.
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_SYNC_DATABASE_URI)

# ----------------------------------------------------------------------
# 3. GIVE ALEMBIC THE MODEL DEFINITIONS
# ----------------------------------------------------------------------
# `Base.metadata` is the catalogue of every table the CODE expects. Alembic
# compares it against what the DATABASE actually has, and the difference
# becomes the migration.
#
# This is why `app/models/__init__.py` imports every model: a model that was
# never imported is absent from this catalogue, so autogenerate would conclude
# its table should be dropped -- or would never create it in the first place.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Generate the SQL without connecting to a database.

    `literal_binds=True` writes values directly into the SQL text rather than
    using bound parameters, because the output is meant to be read and executed
    by a human rather than sent over a connection.
    """
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "pyformat"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Connect to the database and apply the migrations. The normal path.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # No connection pooling: this is a short-lived command-line process
        # that opens one connection and exits. A pool would be pure overhead.
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # ---- ENABLE pgvector BEFORE ANY MIGRATION RUNS ----
        # Postgres does not understand the `vector` type until the extension is
        # created, so the first migration would fail when it reached the
        # embedding column.
        #
        # `IF NOT EXISTS` makes this safe to run every time. Note that the
        # extension must also be AVAILABLE on the server -- which is why
        # docker-compose uses the `pgvector/pgvector:pg16` image rather than
        # plain `postgres:16`.
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Committed immediately, so the extension exists before the migration
        # transaction below begins.
        connection.commit()

        context.configure(connection=connection, target_metadata=target_metadata)

        # Everything inside a single transaction: if any migration fails
        # part-way, the whole batch rolls back and the database is never left
        # in a half-migrated state.
        with context.begin_transaction():
            context.run_migrations()


# Alembic sets the mode based on how it was invoked (the --sql flag selects
# offline). This dispatch runs at import time, because Alembic executes this
# file as a script rather than importing it as a module.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
