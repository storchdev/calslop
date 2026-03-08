export interface SelectOption {
  value: string;
  label: string;
}

export const repeatOptions: SelectOption[] = [
  { value: '', label: 'None' },
  { value: 'FREQ=DAILY', label: 'Daily' },
  { value: 'FREQ=WEEKLY', label: 'Weekly' },
  { value: 'FREQ=MONTHLY', label: 'Monthly' },
  { value: 'FREQ=YEARLY', label: 'Yearly' },
];

export const alertOptions: SelectOption[] = [
  { value: '', label: 'None' },
  { value: '0', label: 'At time' },
  { value: '5', label: '5 minutes before' },
  { value: '10', label: '10 minutes before' },
  { value: '15', label: '15 minutes before' },
  { value: '30', label: '30 minutes before' },
  { value: '60', label: '1 hour before' },
  { value: '120', label: '2 hours before' },
  { value: '1440', label: '1 day before' },
];

export interface AlertSelectState {
  minutes: number[];
  selectValue: string;
  customOption: SelectOption | null;
}

export function formatAlertLabel(minutes: number[]): string {
  return minutes
    .map((m) => {
      if (m === 0) return 'at time';
      if (m % 1440 === 0) return `${m / 1440}d before`;
      if (m % 60 === 0) return `${m / 60}h before`;
      return `${m}m before`;
    })
    .join(', ');
}

export function normalizeAlertMinutes(minutes: number[] | null | undefined): number[] {
  return Array.from(new Set((minutes ?? []).map((m) => Math.max(0, Math.trunc(Number(m)))))).sort((a, b) => a - b);
}

export function buildAlertSelectState(
  minutes: number[] | null | undefined,
  options: ReadonlyArray<SelectOption> = alertOptions
): AlertSelectState {
  const normalized = normalizeAlertMinutes(minutes);
  if (!normalized.length) {
    return { minutes: normalized, selectValue: '', customOption: null };
  }

  if (normalized.length === 1 && options.some((opt) => opt.value === String(normalized[0]))) {
    return { minutes: normalized, selectValue: String(normalized[0]), customOption: null };
  }

  const selectValue = `custom:${normalized.join(',')}`;
  return {
    minutes: normalized,
    selectValue,
    customOption: { value: selectValue, label: `Custom (${formatAlertLabel(normalized)})` },
  };
}

export function resolveAlertMinutesForSubmit(alertSelectValue: string, fallbackMinutes: number[]): number[] {
  if (alertSelectValue && !alertSelectValue.startsWith('custom:')) {
    const value = Number(alertSelectValue);
    if (Number.isFinite(value)) return [Math.max(0, Math.trunc(value))];
  }
  return fallbackMinutes;
}

export function resolveAlertMinutesFromSelection(alertSelectValue: string): number[] | null {
  if (!alertSelectValue) return [];
  if (alertSelectValue.startsWith('custom:')) return null;
  const value = Number(alertSelectValue);
  return Number.isFinite(value) ? [Math.max(0, Math.trunc(value))] : null;
}

export function cycleSelectOption(sel: HTMLSelectElement, dir: 1 | -1): void {
  const options = Array.from(sel.options);
  const index = options.findIndex((option) => option.value === sel.value);
  const next = Math.max(0, Math.min(options.length - 1, index + dir));
  sel.selectedIndex = next;
  sel.value = options[next].value;
  sel.dispatchEvent(new Event('input', { bubbles: true }));
}

export function localNowInput(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hour = String(now.getHours()).padStart(2, '0');
  const minute = String(now.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

export function getPreferredTimezone(timezone: string, includeBrowserFallback = true): string | undefined {
  if (timezone) return timezone;
  if (!includeBrowserFallback) return undefined;
  return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
}
