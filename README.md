# Calslop

A keyboard-first calendar and todo organizer with Svelte 5 (SvelteKit) frontend and Python Flask backend.

## Features

- **Calendar**: Month and day views; subscribe to read-only ICS URL, local folder of .ics files, or CalDAV server
- **Todos**: From local folder and CalDAV (when used); create, complete, edit, delete
- **Keyboard-first**: Switch views (1/C calendar, 2/T todos), day/month (D/M), go to today (G/Home), new (N), j/k or arrows to move focus, Enter to open, ? for shortcuts
- **Theming**: Light, dark, or system

## Quick start

### Backend

```bash
cd backend
uv sync   # or: pip install -e .
uv run flask --app app.main run --port 8000
```

Source config is stored in `~/.config/calslop/sources.json`. To use a different directory (e.g. for development), set `CALSLOP_DATA_DIR` to that path.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 . The dev server proxies `/api` to the backend.

## Install from source (single process, Linux)

Run the app as one process: Flask serves the built Svelte frontend and the API. Default port is **8765** (chosen to avoid common ports like 3000, 5000, 8000, 8080).

**Prerequisites:** Python 3.11+, Node.js 18+, and [uv](https://docs.astral.sh/uv/) (or pip).

1. **Clone and install**

   ```bash
   git clone https://github.com/your-org/calslop.git
   cd calslop
   ```

2. **Backend**

   ```bash
   cd backend
   uv sync   # or: pip install -e .
   cd ..
   ```

3. **Frontend (static build)**

   ```bash
   cd frontend
   npm ci
   npm run build
   cd ..
   ```

4. **Run**

   From the **backend** directory so Flask can import `app.main`. Point `CALSLOP_STATIC_DIR` at the built frontend (use an absolute path):

   ```bash
   cd backend
   CALSLOP_STATIC_DIR="$(realpath ../frontend/build)" uv run flask --app app.main run --port 8765 --host 0.0.0.0
   ```

   Open http://localhost:8765 (or your machine’s IP if remote).

   To use a different port, set the port in the command above and in the systemd unit below.

### systemd service

To run Calslop as a system service (starts on boot, restarts on failure):

1. Create a user to run the app (optional but recommended):

   ```bash
   sudo useradd -r -s /bin/false calslop
   ```

2. Create an install directory, clone the repo, build, and set ownership. Replace `/opt/calslop` with your chosen path if different.

   ```bash
   sudo mkdir -p /opt/calslop
   sudo chown "$USER" /opt/calslop
   git clone https://github.com/your-org/calslop.git /opt/calslop
   cd /opt/calslop
   cd backend && uv sync && cd ..
   cd frontend && npm ci && npm run build && cd ..
   sudo chown -R calslop:calslop /opt/calslop
   sudo mkdir -p /var/lib/calslop
   sudo chown calslop:calslop /var/lib/calslop
   ```

3. Create the systemd unit. Replace `/opt/calslop` in the following with your install path. If you used `pip install -e .` instead of `uv`, set `ExecStart` to your venv’s `python` (e.g. `/opt/calslop/backend/.venv/bin/python`).

   ```bash
   sudo tee /etc/systemd/system/calslop.service << 'EOF'
   [Unit]
   Description=Calslop calendar and todo app
   After=network.target

   [Service]
   Type=simple
   User=calslop
   Group=calslop
   WorkingDirectory=/opt/calslop/backend
   Environment="PYTHONPATH=/opt/calslop/backend"
   Environment="CALSLOP_STATIC_DIR=/opt/calslop/frontend/build"
   Environment="CALSLOP_DATA_DIR=/var/lib/calslop"
   Environment="PATH=/opt/calslop/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin"
   ExecStart=/opt/calslop/backend/.venv/bin/python -m flask --app app.main run --port 8765 --host 0.0.0.0
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   EOF
   ```

4. Enable and start:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable calslop
   sudo systemctl start calslop
   sudo systemctl status calslop
   ```

   The app will be available on port **8765**. Adjust `ExecStart` and any reverse proxy (e.g. nginx) if you use a different port.

### Add a source

1. Open **Settings** and click **Add source**.
2. Choose type:
   - **Read-only ICS URL**: paste a public .ics URL (e.g. from Google Calendar export).
   - **Local .ics folder**: path to a directory; each `.ics` file is one event (or one calendar). Writable: new events/todos create files there.
   - **CalDAV**: server URL, username, password. Events and todos are read/written via CalDAV.

## Project layout

- `backend/` – Flask API: sources CRUD, events/todos aggregation from ICS URL, local folder, and CalDAV; write support for local folder and CalDAV.
- `frontend/` – SvelteKit (Svelte 5) app: calendar (month/day), todo list, modals for create/edit, theme switcher, global keyboard shortcuts.

## API

- `GET/POST/PUT/DELETE /api/sources` – calendar/todo source configs (stored in `~/.config/calslop/sources.json`).
- `GET /api/events?start=&end=` – aggregated events.
- `GET/POST/PATCH/DELETE /api/events[/:id]` – event CRUD (writable sources only).
- `GET /api/todos` – aggregated todos.
- `GET/POST/PATCH/DELETE /api/todos[/:id]` – todo CRUD (writable sources only).
