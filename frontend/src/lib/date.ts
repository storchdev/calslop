/**
 * Get effective timezone: IANA string or undefined for browser local.
 */
export function getTimeZoneOption(tz: string): string | undefined {
  return tz === '' ? undefined : tz;
}

/** Parse ISO string; if no Z or offset, treat as UTC (backend often sends naive UTC). Use for display and timeline positioning. */
export function parseUtcIfNeeded(iso: string): Date {
  const s = iso.trim();
  if (/z$/i.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)) return new Date(s);
  return new Date(s + 'Z');
}

/**
 * Format an ISO date string for use in <input type="datetime-local"> in the chosen timezone.
 */
export function toLocalDatetimeInput(iso: string, timeZone?: string): string {
  const d = parseUtcIfNeeded(iso);
  if (timeZone) {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(d);
    const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
    return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`;
  }
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const h = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${y}-${m}-${day}T${h}:${min}`;
}

/**
 * Format a date/time for display using the given timezone (or browser local if empty).
 */
export function formatInTimezone(
  iso: string,
  options: Intl.DateTimeFormatOptions & { timeZone?: string },
  timeZone?: string,
  timeDisplayFormat: '24h' | '12h' = '24h'
): string {
  const tz = timeZone && timeZone !== '' ? timeZone : undefined;
  return parseUtcIfNeeded(iso).toLocaleString(undefined, {
    ...options,
    hour12: timeDisplayFormat === '12h',
    timeZone: tz,
  });
}

/**
 * Minutes from midnight (00:00) for the given ISO datetime in the specified timezone.
 * Used for positioning events/todos on the day timeline.
 */
export function getMinutesFromMidnight(iso: string, timeZone?: string): number {
  const d = parseUtcIfNeeded(iso);
  const tz = timeZone && timeZone !== '' ? timeZone : undefined;
  const opts: Intl.DateTimeFormatOptions = { hour: 'numeric', minute: 'numeric', hour12: false };
  if (tz) (opts as { timeZone?: string }).timeZone = tz;
  const parts = new Intl.DateTimeFormat('en-CA', opts).formatToParts(d);
  const hour = parseInt(parts.find((p) => p.type === 'hour')?.value ?? '0', 10);
  const minute = parseInt(parts.find((p) => p.type === 'minute')?.value ?? '0', 10);
  return hour * 60 + minute;
}

/**
 * Add days using calendar arithmetic (avoids DST bugs).
 */
export function addDays(d: Date, days: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);
}

/**
 * Add months using calendar arithmetic.
 */
export function addMonths(d: Date, months: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + months, d.getDate());
}
