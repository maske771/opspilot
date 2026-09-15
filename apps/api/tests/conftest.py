import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


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
