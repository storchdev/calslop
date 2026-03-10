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

Shared app config is stored in `~/.config/calslop/settings.json` (sources + notifications). To use a different directory (e.g. for development), set `CALSLOP_DATA_DIR` to that path.

Notification targets:
- `notify_send` (default) for Linux desktop notifications from the backend service
- `webhook` with URL and optional headers
- `email` with recipient in app settings and SMTP credentials from environment variables only

Notification message formatting:
- `time_format` uses Python `strftime` directives (default: `%b %d %H:%M %Z`)
- `body_template` supports multiline text and placeholders: `{time}`, `{delta}`, `{title}`, `{kind}`

Email environment variables (required for `email` target):
- `CALSLOP_EMAIL_SMTP_HOST`
- `CALSLOP_EMAIL_SMTP_PORT`
- `CALSLOP_EMAIL_SMTP_USERNAME`
- `CALSLOP_EMAIL_SMTP_PASSWORD`
- `CALSLOP_EMAIL_USE_TLS` (`1` or `0`, defaults to `1`)
- optional `CALSLOP_EMAIL_FROM`

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

### Recommended: install and update scripts

Clone the repo, then run the install script. It installs to `~/.local/share/calslop` by default (override with a path). Use `--service` to install and enable the systemd user unit.

```bash
git clone https://github.com/storchdev/calslop.git
cd calslop
./install.sh [INSTALL_DIR] [--service]
```

To update an existing install (pull and rebuild), run from the install directory or pass the path:

```bash
./update.sh [INSTALL_DIR]
```

Example: install with systemd user service enabled:

```bash
./install.sh --service
```

### Manual install

The following steps are the manual equivalent of the scripts above.

1. **Clone and install**

   ```bash
   git clone https://github.com/storchdev/calslop.git
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

### systemd user service

To run Calslop as a user service (runs as you, no sudo required):

1. Create an install directory in your home, clone the repo, and build. Example using `~/.local/share/calslop`:

   ```bash
   mkdir -p ~/.local/share/calslop
   git clone https://github.com/storchdev/calslop.git ~/.local/share/calslop
   cd ~/.local/share/calslop
   cd backend && uv sync && cd ..
   cd frontend && npm ci && npm run build && cd ..
   ```

2. Create the user service unit. Uses `%h` for your home directory. If you used a different install path, replace `~/.local/share/calslop` in the unit. If you used `pip install -e .` instead of `uv`, set `ExecStart` to your venv’s `python`.

   ```bash
   mkdir -p ~/.config/systemd/user
   tee ~/.config/systemd/user/calslop.service << 'EOF'
   [Unit]
   Description=Calslop calendar and todo app
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=%h/.local/share/calslop/backend
   Environment="PYTHONPATH=%h/.local/share/calslop/backend"
   Environment="CALSLOP_STATIC_DIR=%h/.local/share/calslop/frontend/build"
   Environment="PATH=%h/.local/share/calslop/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin"
   ExecStart=%h/.local/share/calslop/backend/.venv/bin/python -m flask --app app.main run --port 8765 --host 0.0.0.0
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=default.target
   EOF
   ```

3. Enable and start:

   ```bash
   systemctl --user daemon-reload
   systemctl --user enable calslop
   systemctl --user start calslop
   systemctl --user status calslop
   ```

   The app will be available on port **8765**. Sources and notification settings use the default `~/.config/calslop/settings.json` since the service runs as you.

   To have the service start at boot even when you are not logged in, enable lingering: `loginctl enable-linger $USER`.

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

- `GET/POST/PUT/DELETE /api/sources` – calendar/todo source configs (stored in `~/.config/calslop/settings.json`).
- `GET /api/events?start=&end=` – aggregated events.
- `GET/POST/PATCH/DELETE /api/events[/:id]` – event CRUD (writable sources only).
- `GET /api/todos` – aggregated todos.
- `GET/POST/PATCH/DELETE /api/todos[/:id]` – todo CRUD (writable sources only).
