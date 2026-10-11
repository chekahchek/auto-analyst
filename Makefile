.PHONY: setup lint install-hooks migration migrate eval eval-inspect

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
	@RUN_DEEPEVAL=1 uv --directory backend run deepeval test run tests/deepeval

eval-inspect:
	uv --directory backend run --with 'deepeval[inspect]' deepeval inspect

run:
	uv --directory backend run uvicorn app.main:app --reload

install-hooks:
	cp hooks/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

migration:
	uv --directory backend run alembic revision --autogenerate -m "$(msg)"

migrate:
	uv --directory backend run alembic upgrade head
