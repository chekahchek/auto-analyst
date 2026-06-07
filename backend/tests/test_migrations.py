from sqlalchemy import create_engine, inspect

from app.config import Settings


def test_migration_creates_expected_tables():
    """Verify that running migrations creates all expected tables."""
    settings = Settings.from_ini(app_env="test")
    engine = create_engine(settings.sync_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "user" in tables
    assert "dataset" in tables
    assert "session" in tables
    assert "message" in tables
