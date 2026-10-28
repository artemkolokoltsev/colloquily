.PHONY: dev test lint format-check typecheck check desktop-check build sidecar smoke

dev:
	npm run dev:all

test:
	npm test
	npm run test:quality
	python scripts/test_core.py
	python -m unittest discover -s backend/tests -v

lint:
	npm run lint

format-check:
	npm run format-check

typecheck:
	npm run typecheck

check: lint format-check typecheck test build

desktop-check:
	cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check
	cargo clippy --locked --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
	cargo check --locked --manifest-path src-tauri/Cargo.toml

build:
	npm run build

sidecar:
	python scripts/build_sidecar.py

smoke:
	python scripts/smoke_release.py
