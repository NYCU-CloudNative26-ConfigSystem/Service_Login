"""Database connection and session management"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
from app.core.logging import logger

# Create engine
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=None if settings.debug else None,
    pool_size=10,
    max_overflow=20,
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db():
    """Initialize database - create tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")


async def close_db():
    """Close database connections"""
    engine.dispose()
    logger.info("Database connections closed")
