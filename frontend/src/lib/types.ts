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
}

export type SourceType = 'ics_url' | 'local_folder' | 'caldav';

export interface Source {
  id: string;
  type: SourceType;
  name: string;
  enabled: boolean;
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
}

export interface TodoCreate {
  source_id: string;
  summary: string;
  completed?: boolean;
  due?: string | null;
  description?: string | null;
  priority?: number | null;
  recurrence?: string | null;
}

export interface TodoUpdate {
  summary?: string;
  completed?: boolean;
  due?: string | null;
  description?: string | null;
  priority?: number | null;
  recurrence?: string | null;
}
