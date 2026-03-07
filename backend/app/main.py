import os

from flask import Flask, abort, jsonify, send_from_directory
from flask_cors import CORS
from pydantic import ValidationError

from app.routes import datetime_bp, events_bp, recurrence_bp, todos_bp, sources_bp

app = Flask(__name__)
CORS(
    app,
    origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ],
    allow_headers=["*"],
    supports_credentials=True,
)

app.register_blueprint(events_bp, url_prefix="/api/events")
app.register_blueprint(todos_bp, url_prefix="/api/todos")
app.register_blueprint(sources_bp, url_prefix="/api/sources")
app.register_blueprint(datetime_bp, url_prefix="/api/datetime")
app.register_blueprint(recurrence_bp, url_prefix="/api/recurrence")

# Optional: serve built frontend (single-process install)
STATIC_DIR = os.environ.get("CALSLOP_STATIC_DIR")
if STATIC_DIR and os.path.isdir(STATIC_DIR):
    static_path = os.path.abspath(STATIC_DIR)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path.startswith("api/"):
            return abort(404)
        if path and os.path.isfile(os.path.join(static_path, path)):
            return send_from_directory(static_path, path)
        return send_from_directory(static_path, "index.html")

# Optional: serve built frontend (single-process install)
STATIC_DIR = os.environ.get("CALSLOP_STATIC_DIR")
if STATIC_DIR and os.path.isdir(STATIC_DIR):
    static_path = os.path.abspath(STATIC_DIR)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path.startswith("api/"):
            return abort(404)
        if path and os.path.isfile(os.path.join(static_path, path)):
            return send_from_directory(static_path, path)
        return send_from_directory(static_path, "index.html")


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
def http_error(e):
    return jsonify(detail=getattr(e, "description", str(e))), e.code


@app.errorhandler(ValidationError)
def validation_error(e: ValidationError):
    return jsonify(detail=e.errors()[0].get("msg", str(e))), 400
