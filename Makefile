
.PHONY: up down logs clean shell test

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend worker

clean:
	docker compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +

shell:
	docker exec -it botgpt_api /bin/bash

test:
	docker exec botgpt_api poetry run pytest app/tests/test_api.py -v