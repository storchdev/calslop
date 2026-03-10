from __future__ import annotations

import argparse
import cProfile
import pstats
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ical_utils import parse_todos_from_ical


def build_synthetic_ics(series_count: int, years_back: int) -> str:
    start = datetime.now(timezone.utc) - timedelta(days=365 * years_back)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Calslop Bench//EN"]
    for idx in range(series_count):
        due = (start + timedelta(days=idx % 14)).strftime("%Y%m%dT%H%M%SZ")
        lines.extend(
            [
                "BEGIN:VTODO",
                f"UID:bench-{idx}@example.test",
                f"DUE:{due}",
                "SUMMARY:Synthetic recurring todo",
                "RRULE:FREQ=DAILY",
                "END:VTODO",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\n".join(lines)


def run_profile(series_count: int, years_back: int, runs: int) -> tuple[float, str]:
    ics_text = build_synthetic_ics(series_count, years_back)
    window_start = datetime.now(timezone.utc) - timedelta(days=1)
    window_end = datetime.now(timezone.utc) + timedelta(days=30)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(runs):
        parse_todos_from_ical(
            ics_text,
            source_id="bench-source",
            window_start=window_start,
            window_end=window_end,
        )
    profiler.disable()

    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(25)
    total_seconds = float(getattr(stats, "total_tt", 0.0))
    return total_seconds, stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile recurrence-heavy todo parsing")
    parser.add_argument("--series", type=int, default=300, help="Recurring VTODO series count")
    parser.add_argument("--years-back", type=int, default=5, help="How far in past to start")
    parser.add_argument("--runs", type=int, default=3, help="Number of parse runs")
    args = parser.parse_args()

    total_seconds, stats = run_profile(args.series, args.years_back, args.runs)
    print(f"profile_total_seconds={total_seconds:.4f}")
    print(
        f"profile_series={args.series} profile_years_back={args.years_back} profile_runs={args.runs}"
    )
    print("success_target=drop_dateutil_rrule_cpu_40pct_plus_todo_heavy")
    print(stats)


if __name__ == "__main__":
    main()
