from __future__ import annotations

from zoneinfo import ZoneInfoNotFoundError

from flask import Blueprint, abort, jsonify
from pydantic import BaseModel

from app.routes.utils import parse_json_body
from app.services.human_datetime import parse_human_datetime_to_utc_iso

datetime_bp = Blueprint("datetime", __name__)


class HumanDatetimeParseBody(BaseModel):
    text: str
    timezone: str | None = None
    context_local: str | None = None


@datetime_bp.route("/parse", methods=["POST"])
def parse_human_datetime():
    body = parse_json_body(HumanDatetimeParseBody)

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
