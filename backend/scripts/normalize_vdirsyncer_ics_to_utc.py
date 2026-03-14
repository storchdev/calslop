from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import os
from pathlib import Path
import shutil
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import icalendar


VTODO_TIME_KEYS = {"due", "dtstart", "recurrence-id", "rdate", "exdate"}
VEVENT_TIME_KEYS = {"dtstart", "dtend", "recurrence-id", "rdate", "exdate"}


def _tz_name(tzinfo) -> str:
    return getattr(tzinfo, "key", str(tzinfo))


def _is_utc_datetime(value: Any) -> bool:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return False
    return value.utcoffset() == timedelta(0) and _tz_name(value.tzinfo) in {
        "UTC",
        "UTC+00:00",
        "timezone.utc",
    }


def _is_utc_only_value(value: Any) -> bool:
    if isinstance(value, datetime):
        return _is_utc_datetime(value)
    if isinstance(value, tuple):
        return any(_is_utc_only_value(item) for item in value)
    if hasattr(value, "dts"):
        return any(_is_utc_only_value(getattr(item, "dt", None)) for item in list(value.dts))
    if isinstance(value, list):
        return any(_is_utc_only_value(item) for item in value)
    return False


def _to_tz_aware_local(value: Any, target_tz) -> tuple[Any, bool, bool]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value, False, True
        converted = value.astimezone(target_tz)
        changed = _tz_name(value.tzinfo) != _tz_name(target_tz)
        return converted, changed, True

    if isinstance(value, tuple):
        normalized_items: list[Any] = []
        changed = False
        supported = False
        for item in value:
            normalized_item, item_changed, item_supported = _to_tz_aware_local(item, target_tz)
            normalized_items.append(normalized_item)
            changed = changed or item_changed
            supported = supported or item_supported
        return tuple(normalized_items), changed, supported

    if hasattr(value, "dts"):
        normalized_items: list[Any] = []
        changed = False
        for item in list(value.dts):
            dt_value = getattr(item, "dt", None)
            normalized_item, item_changed, item_supported = _to_tz_aware_local(dt_value, target_tz)
            if not item_supported:
                return value, False, False
            normalized_items.append(normalized_item)
            changed = changed or item_changed
        return normalized_items, changed, True

    if isinstance(value, list):
        normalized_items: list[Any] = []
        changed = False
        supported = False
        for item in value:
            normalized_item, item_changed, item_supported = _to_tz_aware_local(item, target_tz)
            if not item_supported:
                return value, False, False
            if isinstance(normalized_item, list):
                normalized_items.extend(normalized_item)
            else:
                normalized_items.append(normalized_item)
            changed = changed or item_changed
            supported = True
        return normalized_items, changed, supported

    return value, False, False


def normalize_calendar_for_ios_todos(ical_bytes: bytes) -> tuple[bytes, int]:
    target_tz = datetime.now().astimezone().tzinfo
    if target_tz is None:
        raise ValueError("Could not determine local timezone")
    return normalize_calendar_for_ios_todos_in_tz(ical_bytes, target_tz)


def normalize_calendar_for_ios_todos_in_tz(ical_bytes: bytes, target_tz) -> tuple[bytes, int]:
    calendar = icalendar.Calendar.from_ical(ical_bytes)
    changed_properties = 0

    for component in calendar.walk():
        component_name = getattr(component, "name", "")
        if component_name == "VTODO":
            keys_to_process = VTODO_TIME_KEYS
            should_process_event = True
        elif component_name == "VEVENT":
            keys_to_process = VEVENT_TIME_KEYS
            has_rrule = component.get("rrule") is not None
            should_process_event = has_rrule
        else:
            continue

        if not should_process_event:
            continue

        for key in list(component.keys()):
            key_lower = str(key).lower()
            if key_lower not in keys_to_process:
                continue
            try:
                decoded = component.decoded(key)
            except Exception:
                continue

            if component_name == "VEVENT" and not _is_utc_only_value(decoded):
                continue

            normalized, changed, supported = _to_tz_aware_local(decoded, target_tz)
            if not supported or not changed:
                continue

            del component[key]
            if isinstance(normalized, list) and len(normalized) == 1:
                component.add(key, normalized[0])
            else:
                component.add(key, normalized)
            changed_properties += 1

    return calendar.to_ical(), changed_properties


def iter_ics_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.ics") if path.is_file())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite VTODO scheduling datetimes to a single local timezone for iOS Reminders compatibility. VEVENT data is left unchanged to avoid DST recurrence drift."
    )
    parser.add_argument("path", type=Path, help="Path to a vdirsyncer directory")
    parser.add_argument(
        "--tz",
        default="",
        help="Optional IANA timezone override (defaults to system local timezone)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )
    parser.add_argument(
        "--backup-ext",
        default="",
        help="Optional backup extension (example: .bak)",
    )
    return parser.parse_args()


def _resolve_target_timezone(tz_name: str):
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError as exc:
            raise SystemExit(f"Invalid timezone: {tz_name}") from exc

    env_tz = os.environ.get("TZ", "").strip()
    if env_tz:
        try:
            return ZoneInfo(env_tz)
        except ZoneInfoNotFoundError:
            pass

    timezone_file = Path("/etc/timezone")
    if timezone_file.exists():
        try:
            file_tz = timezone_file.read_text(encoding="utf-8").strip()
            if file_tz:
                return ZoneInfo(file_tz)
        except Exception:
            pass

    localtime_path = Path("/etc/localtime")
    try:
        if localtime_path.exists() and localtime_path.is_symlink():
            target = localtime_path.resolve()
            marker = "/zoneinfo/"
            target_str = str(target)
            if marker in target_str:
                file_tz = target_str.split(marker, 1)[1]
                if file_tz:
                    return ZoneInfo(file_tz)
    except Exception:
        pass

    local_tz = datetime.now().astimezone().tzinfo
    if local_tz is None:
        raise SystemExit("Could not determine local timezone")
    return local_tz


def main() -> None:
    args = parse_args()
    root = args.path.expanduser().resolve()
    target_tz = _resolve_target_timezone(args.tz)

    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Directory not found: {root}")

    ics_files = iter_ics_files(root)
    if not ics_files:
        print(f"No .ics files found under {root}")
        return

    changed_files = 0
    changed_properties = 0

    for ics_path in ics_files:
        original = ics_path.read_bytes()
        try:
            rewritten, file_changes = normalize_calendar_for_ios_todos_in_tz(original, target_tz)
        except Exception as exc:
            print(f"ERROR {ics_path}: {exc}")
            continue

        if file_changes == 0 or rewritten == original:
            continue

        changed_files += 1
        changed_properties += file_changes

        if args.dry_run:
            print(f"WOULD UPDATE {ics_path} (properties={file_changes})")
            continue

        if args.backup_ext:
            backup_path = ics_path.with_name(f"{ics_path.name}{args.backup_ext}")
            shutil.copy2(ics_path, backup_path)

        ics_path.write_bytes(rewritten)
        print(f"UPDATED {ics_path} (properties={file_changes})")

    if args.dry_run:
        print(
            f"Done (dry-run): files_to_update={changed_files}, properties_to_update={changed_properties}, scanned={len(ics_files)}"
        )
    else:
        print(
            f"Done: files_updated={changed_files}, properties_updated={changed_properties}, scanned={len(ics_files)}"
        )


if __name__ == "__main__":
    main()
