from __future__ import annotations

from flask import Blueprint, abort, jsonify, request
from pydantic import BaseModel

from app.services.human_alerts import parse_human_alerts


alerts_bp = Blueprint("alerts", __name__)


class HumanAlertsParseBody(BaseModel):
    text: str


@alerts_bp.route("/parse", methods=["POST"])
def parse_human_alerts_route():
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    body = HumanAlertsParseBody.model_validate(data)

    try:
        minutes, label = parse_human_alerts(body.text)
    except ValueError as e:
        abort(400, description=str(e))

    return jsonify({"minutes": minutes, "label": label})
