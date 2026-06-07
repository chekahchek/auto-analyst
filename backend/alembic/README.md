# Alembic Migration Guide

Quick reference for managing database schema migrations in this project.

## How It Works

1. **Models live in `app/models/`**
2. When a `SQLModel` class is defined with `table=True`, it auto-registers into `SQLModel.metadata`
3. `env.py` imports `app.models` and sets `target_metadata = SQLModel.metadata`
4. Alembic compares `target_metadata` against the actual database to generate migrations

## Common Commands

Run all commands from the `backend/` directory (where `alembic.ini` lives).

### Generate a new migration
```bash
alembic revision --autogenerate -m "description of change"
```
Review the generated file in `alembic/versions/` before applying it.

### Apply migrations
```bash
alembic upgrade head        # apply all pending migrations
alembic upgrade +1          # apply only the next pending migration
```

### Rollback migrations
```bash
alembic downgrade -1        # undo the most recent migration
alembic downgrade base      # undo all migrations (empty database)
```

### Check status
```bash
alembic current             # show the current migration on the database
alembic history --verbose   # show full migration chain
```

## File Structure

| File | Purpose |
|------|---------|
| `alembic.ini` | Config: script location, database URL, logging |
| `env.py` | Runtime script: imports models, sets metadata, runs migrations |
| `script.py.mako` | Template used to generate new migration scripts |
| `versions/` | All migration scripts live here |

## Rules of Thumb

- Always review auto-generated migrations before applying them
- Never delete or modify a migration that has already been applied to a shared database
- If a migration fails, the transaction rolls back and `alembic_version` stays unchanged
