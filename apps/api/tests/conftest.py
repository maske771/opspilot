import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.models import Base

MIGRATIONS_DIR = APP_DIR.parents[1] / "database" / "migrations"


@pytest.fixture
def db_session():
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://opspilot:opspilot@localhost:5432/opspilot",
    )
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield session
    engine.dispose()


@pytest.fixture
def webhook_events_table(db_session):
    """`webhook_events` is created by a SQL migration, not by the ORM models, so create it from the real file."""
    migration = MIGRATIONS_DIR / "003_webhook_events.sql"
    if not migration.exists():
        pytest.skip("database/migrations is not available in this environment")
    if db_session.execute(text("SELECT to_regclass('webhook_events')")).scalar() is None:
        db_session.execute(text(migration.read_text()))
        db_session.commit()
