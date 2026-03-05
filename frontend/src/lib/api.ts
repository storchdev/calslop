import type { Event, Todo, Source, EventCreate, EventUpdate, TodoCreate, TodoUpdate } from '$lib/types';

const API = '/api';

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
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
}

export async function getEvents(start?: string, end?: string): Promise<Event[]> {
  const params = new URLSearchParams();
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  const q = params.toString() ? `?${params}` : '';
  return fetchApi<Event[]>(`/events${q}`);
}

export async function getEvent(id: string): Promise<Event> {
  return fetchApi<Event>(`/events/${encodeURIComponent(id)}`);
}

export async function createEvent(data: EventCreate): Promise<Event> {
  return fetchApi<Event>('/events', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateEvent(id: string, data: EventUpdate): Promise<Event> {
  return fetchApi<Event>(`/events/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteEvent(id: string): Promise<void> {
  await fetchApi<unknown>(`/events/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export async function getTodos(): Promise<Todo[]> {
  return fetchApi<Todo[]>('/todos');
}

export async function getTodo(id: string): Promise<Todo> {
  return fetchApi<Todo>(`/todos/${encodeURIComponent(id)}`);
}

export async function createTodo(data: TodoCreate): Promise<Todo> {
  return fetchApi<Todo>('/todos', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateTodo(id: string, data: TodoUpdate): Promise<Todo> {
  return fetchApi<Todo>(`/todos/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteTodo(id: string): Promise<void> {
  await fetchApi<unknown>(`/todos/${encodeURIComponent(id)}`, { method: 'DELETE' });
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
