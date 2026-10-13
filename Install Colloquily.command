#!/bin/zsh
set -e

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

DOCKER_BIN="$(command -v docker || true)"
if [[ -z "$DOCKER_BIN" && -x "/Applications/Docker.app/Contents/Resources/bin/docker" ]]; then
  DOCKER_BIN="/Applications/Docker.app/Contents/Resources/bin/docker"
fi

if [[ -z "$DOCKER_BIN" ]]; then
  echo "Docker Desktop is required. Install or start it, then run this installer again."
  read "?Press Return to close."
  exit 1
fi

echo "Checking local Ollama…"
if ! curl -fsS --max-time 2 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  if [[ -d "/Applications/Ollama.app" ]]; then
    echo "Starting Ollama…"
    open -a Ollama
    for attempt in {1..30}; do
      if curl -fsS --max-time 2 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
  fi
fi

if ! curl -fsS --max-time 2 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "Ollama is not reachable. Start Ollama and wait until 'ollama list' works."
  read "?Press Return to close."
  exit 1
fi

echo "Building and starting Colloquily…"
"$DOCKER_BIN" compose up -d --build
echo "Colloquily is available at http://localhost:8000"
open "http://localhost:8000"
