.PHONY: setup lint install-hooks migration migrate eval

setup:
	uv --directory backend sync

lint:
	uv --directory backend run ruff check .
	uv --directory backend run ruff format .

test:
	uv --directory backend run pytest tests/unit_test --cov=app --cov-report=term-missing

test-integration:
	APP_ENV=test uv --directory backend run pytest tests/integration_test

eval:
	@OPENAI_API_KEY="$$(uv --directory backend run python -c 'from app.config import Settings; print(Settings.from_ini().api_key)')" \
	 OPENAI_API_BASE_URL="$$(uv --directory backend run python -c 'from app.config import Settings; print(Settings.from_ini().api_base_url)')" \
	 OPENCODE_SESSION_ID="$$(uuidgen)" \
	 promptfoo eval -c backend/tests/eval

eval-view:
	promptfoo view

install-hooks:
	cp hooks/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

migration:
	uv --directory backend run alembic revision --autogenerate -m "$(msg)"

migrate:
	uv --directory backend run alembic upgrade head
