"""Tests for database migration flow."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _make_alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_upgrade_and_downgrade(tmp_path: Path):
    """Migrations should create and remove business tables cleanly."""
    database_path = tmp_path / "migration_test.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)

    assert "users" in inspector.get_table_names()
    assert "audit_logs" in inspector.get_table_names()
    assert "alembic_version" in inspector.get_table_names()

    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert version == "0002_add_audit_logs_table"

    command.downgrade(config, "base")

    inspector = inspect(engine)
    assert "users" not in inspector.get_table_names()
    assert "audit_logs" not in inspector.get_table_names()

    assert "alembic_version" in inspector.get_table_names()

    with engine.connect() as connection:
        version_rows = connection.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar_one()

    assert version_rows == 0

    engine.dispose()
