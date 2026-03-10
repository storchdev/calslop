export interface Event {
  id: string;
  source_id: string;
  title: string;
  start: string; // ISO datetime
  end: string;
  all_day: boolean;
  description?: string | null;
  recurrence?: string | null;
  location?: string | null;
  url?: string | null;
  alert_minutes_before?: number[] | null;
  cancelled?: boolean;
}

export interface Todo {
  id: string;
  source_id: string;
  summary: string;
  completed: boolean;
  due?: string | null; // ISO datetime
  description?: string | null;
  priority?: number | null;
  recurrence?: string | null; // RRULE e.g. FREQ=DAILY
  alert_minutes_before?: number[] | null;
}

export type SourceType = 'ics_url' | 'local_folder' | 'caldav';

export interface Source {
  id: string;
  type: SourceType;
  name: string;
  enabled: boolean;
  color?: string | null;
  config: Record<string, unknown>;
}

export interface EventCreate {
  source_id: string;
  title: string;
  start: string;
  end: string;
  all_day?: boolean;
  description?: string | null;
  location?: string | null;
  recurrence?: string | null;
  url?: string | null;
  alert_minutes_before?: number[] | null;
}

export interface EventUpdate {
  title?: string;
  start?: string;
  end?: string;
  all_day?: boolean;
  description?: string | null;
  location?: string | null;
  recurrence?: string | null;
  url?: string | null;
  alert_minutes_before?: number[] | null;
}

export interface TodoCreate {
  source_id: string;
  summary: string;
  completed?: boolean;
  due?: string | null;
  description?: string | null;
  priority?: number | null;
  recurrence?: string | null;
  alert_minutes_before?: number[] | null;
}

export interface TodoUpdate {
  summary?: string;
  completed?: boolean;
  due?: string | null;
  description?: string | null;
  priority?: number | null;
  recurrence?: string | null;
  alert_minutes_before?: number[] | null;
}

export type NotificationTarget = 'notify_send' | 'webhook' | 'email';
export type NotifySendTimeout = '5s' | '15s' | '60s' | 'persistent';

export interface WebhookSettings {
  url?: string | null;
  headers: Record<string, string>;
}

export interface EmailSettings {
  to?: string | null;
}

export interface NotificationSettings {
  enabled: boolean;
  target: NotificationTarget;
  notify_send_timeout: NotifySendTimeout;
  webhook: WebhookSettings;
  email: EmailSettings;
  time_format: string;
  body_template: string;
  health_error?: string;
}

export interface NotificationSettingsUpdate {
  enabled?: boolean;
  target?: NotificationTarget;
  notify_send_timeout?: NotifySendTimeout;
  webhook?: WebhookSettings;
  email?: EmailSettings;
  time_format?: string;
  body_template?: string;
}
