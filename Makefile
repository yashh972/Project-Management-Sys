.PHONY: help up down build rebuild logs ps migrate seed test test-php test-ml lint train forecast backup restore clean

help:
	@echo "Agile CodeBoard development targets"
	@echo "  make up          Build and start app + db + ml"
	@echo "  make down        Stop the stack"
	@echo "  make logs        Tail app and ml logs"
	@echo "  make migrate     Apply database migrations"
	@echo "  make seed        Generate deterministic demo data"
	@echo "  make test        Run PHP and Python tests"
	@echo "  make test-php    Run PHPUnit in the dev container"
	@echo "  make test-ml     Run pytest in the ML container"
	@echo "  make lint        Run phpcs, phpstan and ruff"
	@echo "  make train       Recompute ML insights (legacy bridge)"
	@echo "  make forecast    Forecast the current sprint"
	@echo "  make backup      Dump the MySQL database"
	@echo "  make clean       Remove containers and local build caches"

up:
	@test -f .env || cp .env.example .env
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

rebuild:
	docker compose build --no-cache

logs:
	docker compose logs -f app ml

ps:
	docker compose ps

migrate:
	docker compose exec app php cron/migrate.php

seed:
	docker compose exec app php cron/seed_demo.php

test: test-ml test-php

test-ml:
	docker compose run --rm ml-dev

test-php:
	docker compose run --rm app-dev vendor/bin/phpunit --no-progress

lint:
	docker compose run --rm app-dev vendor/bin/phpcs
	docker compose run --rm app-dev vendor/bin/phpstan
	docker compose run --rm ml-dev ruff check app tests

train:
	docker compose exec app php cron/refresh_ml.php

forecast:
	docker compose exec ml python -c "from app.forecasting import forecast_sprint; print(forecast_sprint(1, 2000))"

backup:
	@mkdir -p backups
	docker compose exec -T db sh -c 'mysqldump -u root -p"$$MYSQL_ROOT_PASSWORD" "$$MYSQL_DATABASE"' > backups/phproject-$$(date +%Y%m%d-%H%M%S).sql

clean:
	docker compose down -v --remove-orphans
	rm -rf ml-service/.pytest_cache ml-service/.ruff_cache
