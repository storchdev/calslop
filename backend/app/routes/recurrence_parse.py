from __future__ import annotations

from flask import Blueprint, abort, jsonify, request
from pydantic import BaseModel

from app.services.human_recurrence import parse_human_recurrence


recurrence_bp = Blueprint("recurrence", __name__)


class HumanRecurrenceParseBody(BaseModel):
    text: str


@recurrence_bp.route("/parse", methods=["POST"])
def parse_human_recurrence_route():
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    body = HumanRecurrenceParseBody.model_validate(data)

    try:
        rrule, label = parse_human_recurrence(body.text)
    except ValueError as e:
        abort(400, description=str(e))

    return jsonify({"rrule": rrule, "label": label})
