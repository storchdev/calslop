from flask import Flask, jsonify
from flask_cors import CORS
from pydantic import ValidationError

from app.routes import events_bp, todos_bp, sources_bp

app = Flask(__name__)
CORS(
    app,
    origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_headers=["*"],
    supports_credentials=True,
)

app.register_blueprint(events_bp, url_prefix="/api/events")
app.register_blueprint(todos_bp, url_prefix="/api/todos")
app.register_blueprint(sources_bp, url_prefix="/api/sources")


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
def http_error(e):
    return jsonify(detail=getattr(e, "description", str(e))), e.code


@app.errorhandler(ValidationError)
def validation_error(e: ValidationError):
    return jsonify(detail=e.errors()[0].get("msg", str(e))), 400
