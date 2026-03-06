from __future__ import annotations

from flask import Blueprint, abort, jsonify, request
from pydantic import BaseModel
from zoneinfo import ZoneInfoNotFoundError

from app.services.human_datetime import parse_human_datetime_to_utc_iso


datetime_bp = Blueprint("datetime", __name__)


class HumanDatetimeParseBody(BaseModel):
    text: str
    timezone: str | None = None
    context_local: str | None = None


@datetime_bp.route("/parse", methods=["POST"])
def parse_human_datetime():
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    body = HumanDatetimeParseBody.model_validate(data)

    try:
        iso, has_date = parse_human_datetime_to_utc_iso(
            body.text,
            body.timezone,
            body.context_local,
        )
    except ZoneInfoNotFoundError:
        abort(400, description="Invalid timezone")
    except ValueError as e:
        abort(400, description=str(e))

    return jsonify({"iso": iso, "has_date": has_date})
