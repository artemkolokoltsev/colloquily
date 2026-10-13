.PHONY: dev test verify ui ui-watch docker-build docker-up docker-down docker-logs

ui:
	npm run build

ui-watch:
	npm run watch:css

dev:
	npm run dev:all

legacy-dev:
	cd meditech_rag && python app.py

test:
	python scripts/test_core.py
	python -m unittest discover -s backend/tests -v

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
