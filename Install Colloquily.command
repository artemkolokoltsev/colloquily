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

echo "Building and starting Colloquily…"
"$DOCKER_BIN" compose up -d --build
echo "Colloquily is available at http://localhost:8000"
open "http://localhost:8000"
