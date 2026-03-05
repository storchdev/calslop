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
