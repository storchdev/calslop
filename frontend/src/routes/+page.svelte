<script lang="ts">
  import { onMount } from 'svelte';
  import type { PageProps } from './$types';
  import { app } from '$lib/stores/app.svelte';
  import Calendar from '$lib/components/Calendar.svelte';
  import TodoList from '$lib/components/TodoList.svelte';
  import EventModal from '$lib/components/EventModal.svelte';
  import TodoModal from '$lib/components/TodoModal.svelte';
  import ShortcutsModal from '$lib/components/ShortcutsModal.svelte';
  import { getEvents, getTodos, updateTodo } from '$lib/api';
  import type { Event, Todo } from '$lib/types';

  let { data }: PageProps = $props();
  let events = $state<Event[]>([]);
  let todos = $state<Todo[]>([]);
  let loading = $state(false);
  let syncing = $state(false);
  let selectedTodo = $state<Todo | null>(null);

  $effect(() => {
    if (data?.events) events = data.events;
    if (data?.todos) todos = data.todos;
  });

  /** Fetch events for a wide range (6 months) and all todos. Only called on initial load and manual Sync. */
  async function refresh() {
    loading = true;
    try {
      const d = app.selectedDate;
      const start = new Date(d.getFullYear(), d.getMonth() - 2, 1).toISOString();
      const end = new Date(d.getFullYear(), d.getMonth() + 4, 0).toISOString();
      const [e, t] = await Promise.all([getEvents(start, end), getTodos()]);
      events = e;
      todos = t;
    } finally {
      loading = false;
    }
  }

  async function sync() {
    if (syncing) return;
    syncing = true;
    try {
      await refresh();
    } finally {
      syncing = false;
    }
  }

  onMount(() => {
    refresh();
  });

  function handleToggleTodo(todo: Todo) {
    updateTodo(todo.id, { completed: !todo.completed }).then(() => {
      todos = todos.map((t) => (t.id === todo.id ? { ...t, completed: !todo.completed } : t));
    });
  }

  function handleSelectTodo(todo: Todo) {
    selectedTodo = todo;
    app.setEditingId(todo.id);
    app.setModalOpen('todo');
  }
</script>

<div class="flex flex-wrap items-center gap-2 py-2 px-4 border-b border-[var(--border)]">
  <button
    class="btn btn-ghost"
    class:bg-[var(--bg-elevated)]={app.viewMode === 'calendar'}
    class:font-semibold={app.viewMode === 'calendar'}
    onclick={() => app.setViewMode('calendar')}
    type="button"
  >
    Calendar
  </button>
  <button
    class="btn btn-ghost"
    class:bg-[var(--bg-elevated)]={app.viewMode === 'todo'}
    class:font-semibold={app.viewMode === 'todo'}
    onclick={() => app.setViewMode('todo')}
    type="button"
  >
    Todos
  </button>
  {#if app.viewMode === 'calendar'}
    <button
      class="btn btn-ghost"
      class:bg-[var(--bg-elevated)]={app.calendarView === 'month'}
      class:font-semibold={app.calendarView === 'month'}
      onclick={() => app.setCalendarView('month')}
      type="button"
    >
      Month
    </button>
    <button
      class="btn btn-ghost"
      class:bg-[var(--bg-elevated)]={app.calendarView === 'day'}
      class:font-semibold={app.calendarView === 'day'}
      onclick={() => app.setCalendarView('day')}
      type="button"
    >
      Day
    </button>
  {/if}
  <button
    class="btn btn-ghost ml-auto"
    type="button"
    disabled={syncing}
    onclick={() => sync()}
    title="Sync calendars and todos"
  >
    {syncing ? 'Syncing…' : 'Sync'}
  </button>
</div>

{#if loading}
  <p class="p-4 text-[var(--text-muted)]">Loading…</p>
{:else if app.viewMode === 'calendar'}
  <Calendar
    events={events}
    selectedDate={app.selectedDate}
    onSelectEvent={(ev) => {
      app.setEditingId(ev.id);
      app.setModalOpen('event');
    }}
  />
{:else}
  <TodoList todos={todos} onToggle={handleToggleTodo} onSelect={handleSelectTodo} />
{/if}

{#if app.modalOpen === 'event'}
  <EventModal onclose={() => { app.setModalOpen(null); app.setEditingId(null); }} onsave={refresh} />
{:else if app.modalOpen === 'todo'}
  <TodoModal
    todoId={app.editingId}
    initialTodo={selectedTodo}
    onclose={() => { app.setModalOpen(null); app.setEditingId(null); selectedTodo = null; }}
    onsave={() => { refresh().then(() => { selectedTodo = null; }); }}
  />
{:else if app.modalOpen === 'shortcuts'}
  <ShortcutsModal onclose={() => app.setModalOpen(null)} />
{/if}
