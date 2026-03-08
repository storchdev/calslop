from __future__ import annotations

from flask import Blueprint, abort, jsonify
from pydantic import BaseModel

from app.routes.utils import parse_json_body
from app.services.human_recurrence import parse_human_recurrence

recurrence_bp = Blueprint("recurrence", __name__)


class HumanRecurrenceParseBody(BaseModel):
    text: str


@recurrence_bp.route("/parse", methods=["POST"])
def parse_human_recurrence_route():
    body = parse_json_body(HumanRecurrenceParseBody)

    try:
        rrule, label = parse_human_recurrence(body.text)
    except ValueError as e:
        abort(400, description=str(e))

    return jsonify({"rrule": rrule, "label": label})
