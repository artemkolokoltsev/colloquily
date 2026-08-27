.PHONY: dev test verify docker-build docker-up docker-down docker-logs

dev:
	cd meditech_rag && python app.py

test:
	cd meditech_rag && python -m unittest discover -s tests -v

verify:
	cd meditech_rag && python scripts/verify_five_day_mvp.py

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f colloquily
