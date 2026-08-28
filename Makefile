DC = docker compose

build-dc:
	$(DC) build

up: build-dc
	$(DC) up -d

debug: build-dc
	$(DC) up

down:
	$(DC) down
