LANGTRACE_COMPOSE = docker compose --env-file .env.langtrace -f docker-compose.langtrace.yml

.PHONY: langtrace-up langtrace-down langtrace-logs dev

langtrace-up:
	$(LANGTRACE_COMPOSE) up -d

langtrace-down:
	$(LANGTRACE_COMPOSE) down

langtrace-logs:
	$(LANGTRACE_COMPOSE) logs -f langtrace

dev:
	cd meditech_rag && python app.py
