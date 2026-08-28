DC = docker compose

build:
	$(DC) build

build-no-cache:
	$(DC) build --no-cache

up: build
	$(DC) up -d

debug: build
	$(DC) up

down:
	$(DC) down
