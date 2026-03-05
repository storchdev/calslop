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

<div class="flex gap-2 py-2 px-4 border-b border-[var(--border)]">
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
    onclose={() => { app.setModalOpen(null); app.setEditingId(null); }}
    onsave={refresh}
  />
{:else if app.modalOpen === 'shortcuts'}
  <ShortcutsModal onclose={() => app.setModalOpen(null)} />
{/if}
