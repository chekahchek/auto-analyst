from app.config import Settings


def test_sync_db_url_replaces_asyncpg():
    settings = Settings(
        app_env="test",
        db_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
    )
    assert (
        settings.sync_db_url
        == "postgresql+psycopg2://postgres:postgres@localhost:5432/test_db"
    )
