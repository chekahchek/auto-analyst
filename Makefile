.PHONY: setup lint install-hooks

setup:
	uv --directory backend sync

lint:
	uv --directory backend run ruff check .
	uv --directory backend run ruff format .

install-hooks:
	cp hooks/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
