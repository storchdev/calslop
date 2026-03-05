<script lang="ts">
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

  $effect(() => {
    if (data?.events) events = data.events;
    if (data?.todos) todos = data.todos;
  });

  async function refresh() {
    loading = true;
    try {
      const start = new Date(app.selectedDate.getFullYear(), app.selectedDate.getMonth(), 1).toISOString();
      const end = new Date(app.selectedDate.getFullYear(), app.selectedDate.getMonth() + 2, 0).toISOString();
      const [e, t] = await Promise.all([getEvents(start, end), getTodos()]);
      events = e;
      todos = t;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    app.selectedDate;
    refresh();
  });

  function handleToggleTodo(todo: Todo) {
    updateTodo(todo.id, { completed: !todo.completed }).then(() => refresh());
  }

  function handleSelectTodo(todo: Todo) {
    app.setEditingId(todo.id);
    app.setModalOpen('todo');
  }
</script>

<div class="view-switcher">
  <button
    class="btn btn-ghost"
    class:active={app.viewMode === 'calendar'}
    onclick={() => app.setViewMode('calendar')}
    type="button"
  >
    Calendar
  </button>
  <button
    class="btn btn-ghost"
    class:active={app.viewMode === 'todo'}
    onclick={() => app.setViewMode('todo')}
    type="button"
  >
    Todos
  </button>
  {#if app.viewMode === 'calendar'}
    <button
      class="btn btn-ghost"
      class:active={app.calendarView === 'month'}
      onclick={() => app.setCalendarView('month')}
      type="button"
    >
      Month
    </button>
    <button
      class="btn btn-ghost"
      class:active={app.calendarView === 'day'}
      onclick={() => app.setCalendarView('day')}
      type="button"
    >
      Day
    </button>
  {/if}
</div>

{#if loading}
  <p class="loading">Loading…</p>
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
    onclose={() => { app.setModalOpen(null); app.setEditingId(null); }}
    onsave={refresh}
  />
{:else if app.modalOpen === 'shortcuts'}
  <ShortcutsModal onclose={() => app.setModalOpen(null)} />
{/if}

<style>
  .view-switcher {
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border-bottom: 1px solid var(--border);
  }
  .view-switcher .btn.active {
    background: var(--bg-elevated);
    font-weight: 600;
  }
  .loading {
    padding: 1rem;
    color: var(--text-muted);
  }
</style>
