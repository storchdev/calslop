import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
  const base = '';
  const [eventsRes, todosRes] = await Promise.all([
    fetch(`${base}/api/events`),
    fetch(`${base}/api/todos`),
  ]);
  const events = eventsRes.ok ? await eventsRes.json() : [];
  const todos = todosRes.ok ? await todosRes.json() : [];
  return { events, todos };
};
