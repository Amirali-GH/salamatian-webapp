.PHONY: dev migrate makemigration test seed lint

dev:
	docker compose up --build

migrate:
	docker compose run --rm web alembic upgrade head

makemigration:
	docker compose run --rm web alembic revision --autogenerate -m "$(m)"

seed:
	docker compose run --rm web python -m app.scripts.seed_admin

test:
	docker compose run --rm web pytest -q --cov=app --cov-report=term-missing

lint:
	ruff check app tests
