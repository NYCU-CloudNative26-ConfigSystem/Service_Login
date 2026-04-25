"""Test configuration and fixtures"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.database.connection import get_db, Base
from app.database.redis import redis_client


# Create test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"
TEST_DB_PATH = Path("test.db")
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    """Create test database and tables"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_test_state():
    """Reset Redis and the SQLite test database around each test."""
    if redis_client._client is not None:
        redis_client._client.flushdb()

    engine.dispose()
    TEST_DB_PATH.unlink(missing_ok=True)

    yield

    if redis_client._client is not None:
        redis_client._client.flushdb()

    app.dependency_overrides.clear()
    engine.dispose()
    TEST_DB_PATH.unlink(missing_ok=True)


@pytest.fixture
def db_session(test_db):
    """Provide a test database session"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    def override_get_db():
        yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session):
    """Provide a test client"""
    return TestClient(app)
