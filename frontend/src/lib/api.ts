import type { Event, Todo, Source, EventCreate, EventUpdate, TodoCreate, TodoUpdate } from '$lib/types';
import { app } from '$lib/stores/app.svelte';

const API = '/api';

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  app.startApiRequest();
  try {
    const res = await fetch(API + path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error((err as { detail?: string }).detail || res.statusText);
    }
    // 204 No Content has no body
    if (res.status === 204) {
      return undefined as T;
    }
    return res.json();
  } finally {
    app.endApiRequest();
  }
}

export async function getEvents(start?: string, end?: string): Promise<Event[]> {
  const params = new URLSearchParams();
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  const q = params.toString() ? `?${params}` : '';
  return fetchApi<Event[]>(`/events${q}`);
}

export async function getEvent(id: string): Promise<Event> {
  return fetchApi<Event>(`/events?${new URLSearchParams({ id })}`);
}

export async function createEvent(data: EventCreate): Promise<Event> {
  return fetchApi<Event>('/events', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateEvent(id: string, data: EventUpdate): Promise<Event> {
  return fetchApi<Event>(`/events?${new URLSearchParams({ id })}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteEvent(id: string): Promise<void> {
  await fetchApi<unknown>(`/events?${new URLSearchParams({ id })}`, { method: 'DELETE' });
}

export async function getTodos(): Promise<Todo[]> {
  return fetchApi<Todo[]>('/todos');
}

export async function getTodo(id: string): Promise<Todo> {
  return fetchApi<Todo>(`/todos?${new URLSearchParams({ id })}`);
}

export async function createTodo(data: TodoCreate): Promise<Todo> {
  return fetchApi<Todo>('/todos', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateTodo(id: string, data: TodoUpdate): Promise<Todo> {
  return fetchApi<Todo>(`/todos?${new URLSearchParams({ id })}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteTodo(id: string): Promise<void> {
  await fetchApi<unknown>(`/todos?${new URLSearchParams({ id })}`, { method: 'DELETE' });
}

export async function getSources(): Promise<Source[]> {
  return fetchApi<Source[]>('/sources');
}

export async function getSource(id: string): Promise<Source> {
  return fetchApi<Source>(`/sources/${encodeURIComponent(id)}`);
}

export async function createSource(data: { type: Source['type']; name: string; enabled?: boolean; config: Record<string, unknown> }): Promise<Source> {
  return fetchApi<Source>('/sources', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateSource(id: string, data: { name?: string; enabled?: boolean; config?: Record<string, unknown> }): Promise<Source> {
  return fetchApi<Source>(`/sources/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteSource(id: string): Promise<void> {
  await fetchApi<unknown>(`/sources/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export async function parseHumanDatetime(
  text: string,
  timezone?: string,
  contextLocal?: string,
): Promise<{ iso: string; hasDate: boolean }> {
  const payload: { text: string; timezone?: string; context_local?: string } = { text };
  if (timezone) payload.timezone = timezone;
  if (contextLocal) payload.context_local = contextLocal;
  const res = await fetchApi<{ iso: string; has_date: boolean }>('/datetime/parse', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return { iso: res.iso, hasDate: res.has_date };
}

export async function parseHumanRecurrence(text: string): Promise<{ rrule: string; label: string }> {
  return fetchApi<{ rrule: string; label: string }>('/recurrence/parse', {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

export async function parseHumanAlerts(text: string): Promise<{ minutes: number[]; label: string }> {
  return fetchApi<{ minutes: number[]; label: string }>('/alerts/parse', {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}
