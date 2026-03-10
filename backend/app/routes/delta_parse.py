from __future__ import annotations

from flask import Blueprint, abort, jsonify
from pydantic import BaseModel

from app.routes.utils import parse_json_body
from app.services.human_delta import parse_human_delta

delta_bp = Blueprint("delta", __name__)


class HumanDeltaParseBody(BaseModel):
    text: str


@delta_bp.route("/parse", methods=["POST"])
def parse_human_delta_route():
    body = parse_json_body(HumanDeltaParseBody)

    try:
        seconds, label = parse_human_delta(body.text)
    except ValueError as e:
        abort(400, description=str(e))

    return jsonify({"seconds": seconds, "label": label})
