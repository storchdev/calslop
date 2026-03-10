#!/usr/bin/env bash
set -e

REPO_URL="${CALSLOP_REPO_URL:-https://github.com/storchdev/calslop.git}"
INSTALL_DIR="$HOME/.local/share/calslop"
INSTALL_SERVICE=false

for arg in "$@"; do
  case "$arg" in
    --service) INSTALL_SERVICE=true ;;
    -*)
      echo "Usage: $0 [INSTALL_DIR] [--service]" >&2
      echo "  INSTALL_DIR  default: \$HOME/.local/share/calslop" >&2
      echo "  --service    install and enable systemd user unit" >&2
      exit 1
      ;;
    *) INSTALL_DIR="$arg" ;;
  esac
done

if [[ -d "$INSTALL_DIR" && -f "$INSTALL_DIR/backend/pyproject.toml" ]]; then
  echo "Directory $INSTALL_DIR already looks like a calslop install. Use update.sh to update." >&2
  exit 1
fi

if [[ -d "$INSTALL_DIR" ]]; then
  echo "Directory $INSTALL_DIR already exists and is not a calslop install." >&2
  exit 1
fi

echo "Installing calslop to $INSTALL_DIR ..."
mkdir -p "$(dirname "$INSTALL_DIR")"
git clone "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "Building backend ..."
cd backend && uv sync && cd ..

echo "Building frontend ..."
cd frontend && npm ci && npm run build && cd ..

echo "Install complete. Run the app with:"
echo "  cd $INSTALL_DIR/backend && CALSLOP_STATIC_DIR=$(realpath ../frontend/build) uv run flask --app app.main run --port 8765 --host 0.0.0.0"
echo ""

if $INSTALL_SERVICE; then
  UNIT_DIR="$HOME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  INSTALL_DIR_ABS="$(cd "$INSTALL_DIR" && pwd)"
  cat > "$UNIT_DIR/calslop.service" << EOF
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
  echo "Systemd user unit installed and enabled. Start with: systemctl --user start calslop"
fi
