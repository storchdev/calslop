#!/usr/bin/env bash
set -e

# Default: first arg, or current dir if we're inside a calslop install, else ~/.local/share/calslop
if [[ -n "${1:-}" ]]; then
  INSTALL_DIR="$1"
elif [[ -f "backend/pyproject.toml" && -d ".git" ]]; then
  INSTALL_DIR="$(pwd)"
else
  INSTALL_DIR="$HOME/.local/share/calslop"
fi

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "Install directory not found: $INSTALL_DIR" >&2
  echo "Usage: $0 [INSTALL_DIR]" >&2
  exit 1
fi

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  echo "Not a git repository: $INSTALL_DIR. Run install.sh first." >&2
  exit 1
fi

echo "Updating calslop in $INSTALL_DIR ..."
cd "$INSTALL_DIR"
git pull

echo "Building backend ..."
cd backend && uv sync && cd ..

echo "Building frontend ..."
cd frontend && npm ci && npm run build && cd ..

if systemctl --user is-active --quiet calslop 2>/dev/null; then
  echo "Restarting systemd user service ..."
  systemctl --user restart calslop
fi

echo "Update complete."
