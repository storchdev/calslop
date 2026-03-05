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
  let selectedEvent = $state<Event | null>(null);

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
      app.setUnsyncedChanges(false);
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
    function onToggleDayTodo(ev: CustomEvent<{ todoId: string }>) {
      const todo = todos.find((t) => t.id === ev.detail.todoId);
      if (todo) handleToggleTodo(todo);
    }
    window.addEventListener('calslop-toggle-day-todo', onToggleDayTodo as EventListener);
    return () => window.removeEventListener('calslop-toggle-day-todo', onToggleDayTodo as EventListener);
  });

  function handleToggleTodo(todo: Todo) {
    updateTodo(todo.id, { completed: !todo.completed }).then(() => {
      todos = todos.map((t) => (t.id === todo.id ? { ...t, completed: !todo.completed } : t));
      app.setUnsyncedChanges(true);
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
    class="btn btn-ghost inline-flex items-baseline gap-1.5"
    class:bg-[var(--bg-elevated)]={app.viewMode === 'calendar'}
    class:font-semibold={app.viewMode === 'calendar'}
    onclick={() => app.setViewMode('calendar')}
    type="button"
  >
    Calendar
    <span class="key-hint">1</span>
  </button>
  <button
    class="btn btn-ghost inline-flex items-baseline gap-1.5"
    class:bg-[var(--bg-elevated)]={app.viewMode === 'todo'}
    class:font-semibold={app.viewMode === 'todo'}
    onclick={() => app.setViewMode('todo')}
    type="button"
  >
    Todos
    <span class="key-hint">2</span>
  </button>
  {#if app.viewMode === 'calendar'}
    <button
      class="btn btn-ghost inline-flex items-baseline gap-1.5"
      class:bg-[var(--bg-elevated)]={app.calendarView === 'month'}
      class:font-semibold={app.calendarView === 'month'}
      onclick={() => app.setCalendarView('month')}
      type="button"
    >
      Month
      <span class="key-hint">M</span>
    </button>
    <button
      class="btn btn-ghost inline-flex items-baseline gap-1.5"
      class:bg-[var(--bg-elevated)]={app.calendarView === 'day'}
      class:font-semibold={app.calendarView === 'day'}
      onclick={() => app.setCalendarView('day')}
      type="button"
    >
      Day
      <span class="key-hint">D</span>
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

<div class="flex flex-1 flex-col min-h-0">
  {#if loading}
    <p class="p-4 text-[var(--text-muted)]">Loading…</p>
  {:else if app.viewMode === 'calendar'}
    <div class="flex flex-1 flex-col min-h-0 gap-2">
      <div class="flex flex-wrap items-center gap-2 px-4 shrink-0">
      <label class="flex items-center gap-2 text-sm text-[var(--text-muted)]">
        <span>View:</span>
        <select
          class="rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm text-[var(--text)]"
          value={app.calendarDensity}
          onchange={(e) => app.setCalendarDensity((e.currentTarget as HTMLSelectElement).value as 'minimal' | 'balanced' | 'dense')}
        >
          <option value="minimal">Minimal</option>
          <option value="balanced">Balanced</option>
          <option value="dense">Dense</option>
        </select>
      </label>
      {#if app.calendarDensity !== 'minimal'}
        <label class="inline-flex items-center gap-2 cursor-pointer text-sm">
          <input type="checkbox" checked={app.showTodosOnCalendar} onchange={() => app.toggleShowTodosOnCalendar()} />
          <span>Show todos on calendar</span>
        </label>
      {/if}
      </div>
      <div class="flex-1 min-h-0 flex flex-col">
        <Calendar
      events={events}
      todos={todos}
      selectedDate={app.selectedDate}
      onSelectEvent={(ev) => {
        selectedEvent = ev;
        app.setEditingId(ev.id);
        app.setModalOpen('event');
      }}
      onSelectTodo={(todo) => {
        selectedTodo = todo;
        app.setEditingId(todo.id);
        app.setModalOpen('todo');
      }}
        />
      </div>
    </div>
  {:else}
    <TodoList
    todos={todos}
    showCompleted={app.showCompletedTodos}
    todoOrder={app.todoOrder}
    onToggle={handleToggleTodo}
    onSelect={handleSelectTodo}
  />
  {/if}
</div>

{#if app.hasUnsyncedChanges}
  <div class="unsynced-notifier" role="status">
    Unsaved changes — Sync or refresh to update
  </div>
{/if}

{#if app.modalOpen === 'event'}
  <EventModal
    initialEvent={selectedEvent}
    onclose={() => { app.setModalOpen(null); app.setEditingId(null); selectedEvent = null; }}
    onsave={refresh}
  />
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
