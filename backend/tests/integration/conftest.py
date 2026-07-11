import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import get_engine


@pytest.fixture(scope="module")
def db_session():
    command.upgrade(Config("alembic.ini"), "head")
    engine = get_engine()
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        get_engine.cache_clear()
