.PHONY: dev test build sidecar smoke

dev:
	npm run dev:all

test:
	npm test
	python scripts/test_core.py
	python -m unittest discover -s backend/tests -v

build:
	npm run build

sidecar:
	python scripts/build_sidecar.py

smoke:
	python scripts/smoke_release.py
