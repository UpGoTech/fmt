#!/usr/bin/env bash
# Install fmt (Frappe Manager - Traefik).  Usage: curl -fsSL <raw install.sh url> | bash
set -Eeuo pipefail

REPOSITORY="${FMT_REPOSITORY:-https://github.com/UpGoTech/fmt}"
REFERENCE="${FMT_REF:-develop}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "error: $1 is required. $2" >&2; exit 1; }; }

need docker "Install Docker: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || { echo "error: Docker Compose v2 plugin is required" >&2; exit 1; }
need git "Install it with: apt-get install -y git"
need openssl "Install it with: apt-get install -y openssl"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv tool install --force "git+${REPOSITORY}@${REFERENCE}"
uv tool update-shell >/dev/null 2>&1 || true

echo
echo "fmt installed. Open a new shell (or: export PATH=\"\$HOME/.local/bin:\$PATH\") and run:"
echo "  fmt doctor"
echo "  fmt create erp.example.com"
