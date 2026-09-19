.PHONY: help up down restart logs ps migrate revision run test clean
help:
@echo "QuickCart - common commands"
@echo "  make up         Start Postgres + Redis in Docker"
@echo "  make down       Stop containers"
@echo "  make logs       Tail container logs"
@echo "  make migrate    Apply Alembic migrations"
@echo "  make revision m='msg'  Create new migration"
@echo "  make run        Run FastAPI dev server"
@echo "  make test       Run pytest"
up:
docker compose up -d
down:
docker compose down
restart:
docker compose restart
logs:
docker compose logs -f
ps:
docker compose ps
migrate:
alembic upgrade head
revision:
alembic revision --autogenerate -m "$(m)"
run:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
test:
pytest -v
clean:
docker compose down -v
