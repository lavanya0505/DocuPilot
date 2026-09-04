"""
base_class.py
=============
WHAT THIS FILE DOES
-------------------
Defines `Base`, the parent class that EVERY database model inherits from.

    class User(Base): ...
    class Document(Base): ...

Inheriting from Base is what makes SQLAlchemy treat a plain Python class as a
database table: it collects the columns you declare and registers the table in
a shared catalogue called the metadata.

WHY THAT CATALOGUE MATTERS
--------------------------
Alembic reads `Base.metadata` to discover every table the code expects. That is
how `alembic revision --autogenerate` can compare your models against the real
database and write a migration for the difference.

It is also why `app/models/__init__.py` imports every model: a model that is
never imported never registers itself, so Alembic would silently omit its table
from the migration.

THE ONE CLEVER BIT: AUTOMATIC TABLE NAMES
-----------------------------------------
Rather than writing `__tablename__ = "chunk_embeddings"` on every model, the
name is derived from the class name:

        ChunkEmbedding  ->  chunk_embeddings
        User            ->  users
        Category        ->  categories

Less repetition, and no chance of a typo silently creating a second table.
"""

import re
from typing import Any

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """The shared parent of every table in this application."""

    # These are type-checker hints, not columns. They tell tools that every
    # subclass will have an `id` and a `__name__`, so the code below is valid.
    id: Any
    __name__: str

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """
        Build the table name from the class name.

        `@declared_attr.directive` tells SQLAlchemy to CALL this method for each
        subclass and use the result as that subclass's table name, instead of
        treating it as a normal attribute.

        Worked example, for `ChunkEmbedding`:

            1. name  = "ChunkEmbedding"
            2. snake = "chunk_embedding"      (regex explained below)
            3. does not end in 'y' or 's', so append 's'
            4. result: "chunk_embeddings"
        """
        name = cls.__name__

        # ---- CamelCase -> snake_case ----
        # `(?<!^)` is a negative lookbehind meaning "not at the very start", so
        # we do not put an underscore before the first capital letter.
        # `(?=[A-Z])` is a lookahead matching the empty position just before any
        # capital. Together they insert "_" before each internal capital:
        #     "ChunkEmbedding" -> "Chunk_Embedding" -> lower -> "chunk_embedding"
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

        # ---- Simple pluralisation ----
        # Enough for this schema's vocabulary. English plurals are wildly
        # irregular in general, so any model needing something else should just
        # set `__tablename__` explicitly -- as APIKey does, because this rule
        # would otherwise turn it into the unreadable "a_p_i_keys".
        if snake.endswith("y"):
            # category -> categories
            return snake[:-1] + "ies"
        elif snake.endswith("s"):
            # Already plural; leave it alone.
            return snake
        else:
            return snake + "s"
