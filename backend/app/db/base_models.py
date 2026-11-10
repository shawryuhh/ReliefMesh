"""Import point for all ORM models.

Alembic's env.py imports this module so that every model is registered on
Base.metadata before autogenerate runs.
"""

from app.db.base import Base  # noqa: F401
from app.models.action_log import ActionLog  # noqa: F401
from app.models.assignment import Assignment  # noqa: F401
from app.models.incident import Incident  # noqa: F401
from app.models.recommendation import Recommendation  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.resource import Resource  # noqa: F401
