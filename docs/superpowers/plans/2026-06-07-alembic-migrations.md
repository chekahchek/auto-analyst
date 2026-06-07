# Alembic Migrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up Alembic for database migrations in the Auto-Analyst backend, including the first migration covering all existing SQLModel models.

**Architecture:** A sync-driver Alembic configuration derived from the existing async DB URL. Migrations run via CLI or an optional docker-compose one-shot service. Tests verify both the sync URL conversion and that migrations create the expected schema.

**Tech Stack:** FastAPI, SQLModel, SQLAlchemy, Alembic, psycopg2-binary, pytest

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/pyproject.toml` | Add `alembic` and `psycopg2-binary` dependencies |
| `backend/app/config.py` | Add `sync_db_url` property to `Settings` |
| `backend/tests/test_config.py` | Unit test for `sync_db_url` |
| `backend/alembic.ini` | Alembic configuration (trimmed) |
| `backend/alembic/env.py` | Alembic runtime: sync engine, metadata, URL from config |
| `backend/alembic/script.py.mako` | Migration script template (default, no changes) |
| `backend/alembic/versions/` | Migration scripts directory |
| `backend/docker-compose.yml` | Add optional `migrator` service |
| `backend/tests/conftest.py` | Add `apply_migrations` session fixture |
| `backend/tests/test_migrations.py` | Integration test: verify migrations create tables |

---

### Task 1: Add Dependencies

**Files:**
- Modify: `backend/pyproject.toml`
- Test: (none — dependency addition)

- [ ] **Step 1: Add `alembic` and `psycopg2-binary` to dev dependencies**

Replace the `[dependency-groups]` section in `backend/pyproject.toml` with:

```toml
[dependency-groups]
dev = [
    "alembic>=1.15.0",
    "ipykernel>=7.2.0",
    "jupyterlab>=4.5.7",
    "psycopg2-binary>=2.9.10",
    "pytest-asyncio>=0.25.0",
    "python-dotenv>=1.2.2",
    "ruff>=0.15.16",
]
```

- [ ] **Step 2: Sync dependencies**

Run:
```bash
cd backend
uv sync
```

Expected: `alembic` and `psycopg2-binary` installed in `.venv`.

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "deps: add alembic and psycopg2-binary"
```

---

### Task 2: sync_db_url Property (TDD)

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_config.py` with:

```python
from app.config import Settings


def test_sync_db_url_replaces_asyncpg():
    settings = Settings(
        app_env="test",
        db_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
    )
    assert settings.sync_db_url == "postgresql+psycopg2://postgres:postgres@localhost:5432/test_db"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend
uv run pytest tests/test_config.py::test_sync_db_url_replaces_asyncpg -v
```

Expected: `FAILED` — `AttributeError: 'Settings' object has no attribute 'sync_db_url'`

- [ ] **Step 3: Add `sync_db_url` property to `Settings`**

In `backend/app/config.py`, add this property inside the `Settings` class (after the `skills_dir` field and before the `from_ini` method):

```python
    @property
    def sync_db_url(self) -> str:
        """Return a sync-driver URL for Alembic / admin tools."""
        return self.db_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd backend
uv run pytest tests/test_config.py::test_sync_db_url_replaces_asyncpg -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(config): add sync_db_url property for Alembic"
```

---

### Task 3: Initialise Alembic

**Files:**
- Create: `backend/alembic/` (directory and contents)
- Create: `backend/alembic.ini`

- [ ] **Step 1: Run `alembic init`**

Run:
```bash
cd backend
uv run alembic init alembic
```

Expected output:
```
Creating directory /.../backend/alembic ...  done
Creating directory /.../backend/alembic/versions ...  done
Generating /.../backend/alembic.ini ...  done
Generating /.../backend/alembic/env.py ...  done
Generating /.../backend/alembic/script.py.mako ...  done
Done!
```

- [ ] **Step 2: Verify directory structure**

Run:
```bash
ls -la backend/alembic/
```

Expected: `env.py`, `README`, `script.py.mako`, `versions/`

- [ ] **Step 3: Commit raw init output**

```bash
git add backend/alembic backend/alembic.ini
git commit -m "chore(alembic): initialise alembic"
```

---

### Task 4: Configure `alembic/env.py`

**Files:**
- Modify: `backend/alembic/env.py`

- [ ] **Step 1: Replace generated `env.py`**

Replace the entire contents of `backend/alembic/env.py` with:

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from sqlmodel import SQLModel

# Import all models so SQLModel.metadata is populated
import app.models  # noqa: F401
from app.config import Settings

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL from application settings
settings = Settings.from_ini()
config.set_main_option("sqlalchemy.url", settings.sync_db_url)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 2: Commit**

```bash
git add backend/alembic/env.py
git commit -m "feat(alembic): configure env.py with sync engine and SQLModel metadata"
```

---

### Task 5: Trim `alembic.ini`

**Files:**
- Modify: `backend/alembic.ini`

- [ ] **Step 1: Replace with trimmed configuration**

Replace the entire contents of `backend/alembic.ini` with:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Commit**

```bash
git add backend/alembic.ini
git commit -m "chore(alembic): trim alembic.ini to essentials"
```

---

### Task 6: Add `migrator` Service to docker-compose

**Files:**
- Modify: `backend/docker-compose.yml`

- [ ] **Step 1: Replace docker-compose.yml**

Replace the entire contents of `backend/docker-compose.yml` with:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: auto_analyst
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d auto_analyst"]
      interval: 5s
      timeout: 5s
      retries: 5

  migrator:
    build:
      context: ..
      dockerfile: backend/Dockerfile
    command: ["sh", "-c", "cd backend && alembic upgrade head"]
    depends_on:
      db:
        condition: service_healthy
    environment:
      APP_ENV: dev
    volumes:
      - ..:/app
    profiles: ["migrate"]

volumes:
  postgres_data:
```

- [ ] **Step 2: Commit**

```bash
git add backend/docker-compose.yml
git commit -m "chore(docker): add migrator one-shot service with profile"
```

---

### Task 7: Add `apply_migrations` Fixture

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add fixture to `conftest.py`**

Replace the entire contents of `backend/tests/conftest.py` with:

```python
import asyncio

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    """Run Alembic migrations before the test session."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test(conftest): add apply_migrations session fixture"
```

---

### Task 8: Generate First Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_initial_schema.py`

- [ ] **Step 1: Generate migration**

Run:
```bash
cd backend
uv run alembic revision --autogenerate -m "Initial schema"
```

Expected: A new file created in `alembic/versions/` with a name like `2026_06_07_1200_initial_schema.py`.

- [ ] **Step 2: Inspect generated migration**

Open the generated file and verify:
- `create_table('user', ...)` exists with `email` column
- `create_table('dataset', ...)` exists with `user_id` foreign key
- `create_table('session', ...)` exists with `dataset_id` foreign key
- `create_table('message', ...)` exists with `session_id` foreign key
- Indexes and constraints are present

If any table or relationship is missing, check that the model module is imported in `env.py` and that `table=True` is set on each model.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(migrations): add initial schema migration"
```

---

### Task 9: Migration Integration Test

**Files:**
- Create: `backend/tests/test_migrations.py`

**Prerequisite:** Postgres must be running. Start it with:
```bash
cd backend
docker compose up -d db
```

- [ ] **Step 1: Write integration test**

Create `backend/tests/test_migrations.py` with:

```python
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
```

- [ ] **Step 2: Run test**

Run:
```bash
cd backend
uv run pytest tests/test_migrations.py::test_migration_creates_expected_tables -v
```

Expected: `PASSED` (the `apply_migrations` autouse fixture already applied the migration before this test).

If it fails with tables missing, ensure the DB is running and run `uv run alembic upgrade head` manually, then re-run the test.

- [ ] **Step 3: Run full test suite**

Run:
```bash
cd backend
uv run pytest -v
```

Expected: All tests pass. The `apply_migrations` fixture runs once before the session.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_migrations.py
git commit -m "test(migrations): add integration test for schema tables"
```

---

## Self-Review Checklist

### 1. Spec Coverage

| Spec Requirement | Plan Task |
|---|---|
| Add `alembic` dependency | Task 1 |
| Add `psycopg2-binary` dependency | Task 1 |
| Add `sync_db_url` property | Task 2 |
| Initialise Alembic | Task 3 |
| Configure `env.py` with sync engine | Task 4 |
| Trim `alembic.ini` | Task 5 |
| Add `migrator` service to docker-compose | Task 6 |
| Add `apply_migrations` fixture | Task 7 |
| Generate first migration | Task 8 |
| Test migration creates tables | Task 9 |

All spec requirements covered. No gaps.

### 2. Placeholder Scan

- No "TBD", "TODO", or "implement later" found.
- No vague instructions like "add appropriate error handling".
- Every step has exact file paths, complete code, and exact commands.
- No "similar to Task N" references.

### 3. Type Consistency

- `sync_db_url` returns `str` in both config property and test assertion.
- `Settings.from_ini(app_env="test")` used consistently in tests.
- `alembic_cfg = Config("alembic.ini")` used consistently in fixture and tests.
- All model names match (`User`, `Dataset`, `Session`, `Message`).
