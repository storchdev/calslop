/**
 * Get effective timezone: IANA string or undefined for browser local.
 */
export function getTimeZoneOption(tz: string): string | undefined {
  return tz === '' ? undefined : tz;
}

/**
 * Format an ISO date string for use in <input type="datetime-local"> in the chosen timezone.
 */
export function toLocalDatetimeInput(iso: string, timeZone?: string): string {
  const d = new Date(iso);
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
  timeZone?: string
): string {
  const tz = timeZone && timeZone !== '' ? timeZone : undefined;
  return new Date(iso).toLocaleString(undefined, { ...options, timeZone: tz });
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
