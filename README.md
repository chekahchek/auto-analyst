

## Starting Database
1. Start PostgresSQL
```bash
cd backend
docker compose up -d db
```

2. Apply migrations
```bash
uv run alembic upgrade head
uv run alembic current
```

3. Check Database
```bash
docker compose exec db psql -U postgres -d auto_analyst
```