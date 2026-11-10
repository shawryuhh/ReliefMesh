from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models.

    Models are imported in app/db/base_models.py so Alembic's autogenerate
    can discover them via Base.metadata without main.py needing to import
    every model module directly.
    """
