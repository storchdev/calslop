#!/usr/bin/env bash
set -e

REPO_URL="${CALSLOP_REPO_URL:-https://github.com/storchdev/calslop.git}"
INSTALL_DIR="$HOME/.local/share/calslop"
INSTALL_SERVICE=true # default: install the systemd service

for arg in "$@"; do
  case "$arg" in
  --service) INSTALL_SERVICE=true ;;
  --no-service) INSTALL_SERVICE=false ;;
  -*)
    echo "Usage: $0 [INSTALL_DIR] [--no-service]" >&2
    echo "  INSTALL_DIR   default: \$HOME/.local/share/calslop" >&2
    echo "  --no-service  skip installing the systemd user unit" >&2
    exit 1
    ;;
  *) INSTALL_DIR="$arg" ;;
  esac
done

if [[ -d "$INSTALL_DIR" && -f "$INSTALL_DIR/backend/pyproject.toml" ]]; then
  echo "Directory $INSTALL_DIR already looks like a calslop install. Use 'calslop update' to update." >&2
  exit 1
fi

if [[ -d "$INSTALL_DIR" ]]; then
  echo "Directory $INSTALL_DIR already exists and is not a calslop install." >&2
  exit 1
fi

missing_deps=()
for dep in git uv npm; do
  if ! command -v "$dep" &>/dev/null; then
    missing_deps+=("$dep")
  fi
done
if [[ ${#missing_deps[@]} -gt 0 ]]; then
  echo "Error: the following required dependencies are not installed: ${missing_deps[*]}" >&2
  echo "Please install them and re-run this script." >&2
  exit 1
fi

echo "Installing calslop to $INSTALL_DIR ..."
mkdir -p "$(dirname "$INSTALL_DIR")"
git clone "$REPO_URL" "$INSTALL_DIR"

echo "Building backend ..."
cd "$INSTALL_DIR/backend" && uv sync && cd ..

echo "Building frontend ..."
cd "$INSTALL_DIR/frontend" && npm ci && npm run build && cd ..

# Install the calslop management script to ~/.local/bin
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
install -m 0755 "$INSTALL_DIR/bin/calslop" "$BIN_DIR/calslop"
echo ""
echo "calslop management script installed to: $BIN_DIR/calslop"
echo "(Make sure $BIN_DIR is in your PATH)"
echo ""

if $INSTALL_SERVICE; then
  UNIT_DIR="$HOME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  INSTALL_DIR_ABS="$(cd "$INSTALL_DIR" && pwd)"
  cat >"$UNIT_DIR/calslop.service" <<EOF
[Unit]
Description=Calslop calendar and todo app
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR_ABS/backend
Environment="PYTHONPATH=$INSTALL_DIR_ABS/backend"
Environment="CALSLOP_STATIC_DIR=$INSTALL_DIR_ABS/frontend/build"
# Environment="CALSLOP_EMAIL_SMTP_HOST=smtp.example.com"
# Environment="CALSLOP_EMAIL_SMTP_PORT=587"
# Environment="CALSLOP_EMAIL_SMTP_USERNAME=you@example.com"
# Environment="CALSLOP_EMAIL_SMTP_PASSWORD=app-password"
# Environment="CALSLOP_EMAIL_USE_TLS=1"
# Environment="CALSLOP_EMAIL_FROM=you@example.com"
Environment="PATH=$INSTALL_DIR_ABS/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$INSTALL_DIR_ABS/backend/.venv/bin/python -m flask --app app.main run --port 8765 --host 0.0.0.0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable calslop
  echo "Systemd user unit installed and enabled."
  echo ""
fi

echo "Install complete."
echo ""
echo "Usage:"
echo "  calslop start          Start the service"
echo "  calslop stop           Stop the service"
echo "  calslop status         Check service status"
echo "  calslop logs -f        Follow service logs"
echo "  calslop update         Pull latest code and rebuild"
echo "  calslop help           Show all commands"
