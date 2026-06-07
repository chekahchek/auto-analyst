# from sqlalchemy import create_engine, inspect

# from app.config import Settings


# def test_migration_creates_expected_tables():
#     """Verify that running migrations creates all expected tables, indexes, and constraints."""
#     settings = Settings.from_ini(app_env="test")
#     engine = create_engine(settings.sync_db_url)
#     try:
#         inspector = inspect(engine)
#         tables = inspector.get_table_names()

#         assert "user" in tables, f"Expected table 'user' not found in {tables}"
#         assert "dataset" in tables, f"Expected table 'dataset' not found in {tables}"
#         assert "session" in tables, f"Expected table 'session' not found in {tables}"
#         assert "message" in tables, f"Expected table 'message' not found in {tables}"

#         # Verify at least one index exists
#         user_indexes = {idx["name"] for idx in inspector.get_indexes("user")}
#         assert "ix_user_email" in user_indexes, (
#             f"Expected index 'ix_user_email' not found in {user_indexes}"
#         )

#         # Verify at least one foreign key exists
#         dataset_fks = {fk["name"] for fk in inspector.get_foreign_keys("dataset")}
#         assert len(dataset_fks) > 0, "Expected at least one foreign key on 'dataset'"
#     finally:
#         engine.dispose()
