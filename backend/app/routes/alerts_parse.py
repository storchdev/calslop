from __future__ import annotations

from flask import Blueprint, abort, jsonify
from pydantic import BaseModel

from app.routes.utils import parse_json_body
from app.services.human_alerts import parse_human_alerts

alerts_bp = Blueprint("alerts", __name__)


class HumanAlertsParseBody(BaseModel):
    text: str


@alerts_bp.route("/parse", methods=["POST"])
def parse_human_alerts_route():
    body = parse_json_body(HumanAlertsParseBody)

    try:
        minutes, label = parse_human_alerts(body.text)
    except ValueError as e:
        abort(400, description=str(e))

    return jsonify({"minutes": minutes, "label": label})
