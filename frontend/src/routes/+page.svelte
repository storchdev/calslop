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
    const hasData = events.length > 0 || todos.length > 0;
    if (!hasData) loading = true;
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
    function onSync() {
      sync();
    }
    window.addEventListener('calslop-toggle-day-todo', onToggleDayTodo as EventListener);
    window.addEventListener('calslop-sync', onSync);
    return () => {
      window.removeEventListener('calslop-toggle-day-todo', onToggleDayTodo as EventListener);
      window.removeEventListener('calslop-sync', onSync);
    };
  });

  let togglingTodoId = $state<string | null>(null);

  async function handleToggleTodo(todo: Todo) {
    if (togglingTodoId === todo.id) return;
    const nextCompleted = !todo.completed;
    togglingTodoId = todo.id;
    if (todo.recurrence) {
      // Recurring: replace row with loading until update + refetch complete
      try {
        await updateTodo(todo.id, { completed: nextCompleted });
        await refresh();
      } catch {
        // Revert not needed; we didn't change local state
      } finally {
        togglingTodoId = null;
      }
      return;
    }
    // Non-recurring: optimistic update + immediate server save
    const prev = todos;
    todos = todos.map((t) => (t.id === todo.id ? { ...t, completed: nextCompleted } : t));
    try {
      await updateTodo(todo.id, { completed: nextCompleted });
      app.setUnsyncedChanges(false);
    } catch {
      todos = prev;
    } finally {
      togglingTodoId = null;
    }
  }

  function handleSelectTodo(todo: Todo) {
    selectedTodo = todo;
    app.setEditingId(todo.id);
    app.setModalOpen('todo');
  }
</script>

<div class="main-content flex flex-1 flex-col min-h-0">
  {#if app.viewMode === 'calendar'}
    <div class="flex flex-1 flex-col min-h-0">
      <div class="subtoolbar flex flex-wrap items-center gap-3 px-4 py-3 shrink-0">
        {#if loading}
          <span class="text-sm text-[var(--text-muted)]" role="status" aria-live="polite">Loading…</span>
        {/if}
        <div class="dropdown-box">
          <span class="dropdown-box-label dropdown-box-label-with-key"><span>View</span><span class="key-hint">V</span></span>
          <select
            value={app.calendarDensity}
            onchange={(e) => app.setCalendarDensity((e.currentTarget as HTMLSelectElement).value as 'minimal' | 'balanced' | 'dense')}
          >
            <option value="minimal">Minimal</option>
            <option value="balanced">Balanced</option>
            <option value="dense">Dense</option>
          </select>
        </div>
        {#if app.calendarDensity !== 'minimal'}
          <div class="option-box">
            <span class="dropdown-box-label">Show todos</span>
            <label class="option-box-content inline-flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={app.showTodosOnCalendar} onchange={() => app.toggleShowTodosOnCalendar()} />
              <span class="key-hint">Y</span>
            </label>
          </div>
        {/if}
        <div class="option-box">
          <span class="dropdown-box-label">Height</span>
          <div class="option-box-content flex items-center gap-2">
            <input
              type="range"
              class="calendar-height-slider"
              min="1"
              max="3"
              step="0.05"
              value={app.calendarHeightRatio}
              oninput={(e) => app.setCalendarHeightRatio(+(e.currentTarget as HTMLInputElement).value)}
              title="Calendar height (100–300%)"
            />
            <span class="text-xs text-[var(--text-muted)]">{Math.round(app.calendarHeightRatio * 100)}%</span>
          </div>
        </div>
        {#if app.calendarView === 'month'}
          <span class="search-input-wrap">
            <input
              id="calslop-search-input"
              type="search"
              class="search-input"
              placeholder="Search…"
              value={app.searchInputValue}
              oninput={(e) => app.setSearchInputValue((e.currentTarget as HTMLInputElement).value)}
              onkeydown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  app.applySearch();
                  (e.currentTarget as HTMLInputElement).blur();
                }
                if (e.key === 'Escape') {
                  e.preventDefault();
                  app.clearSearch();
                  (e.currentTarget as HTMLInputElement).blur();
                }
              }}
              title="Search events and todos (/ to focus, Enter to filter, Escape to exit search)"
              aria-label="Search events and todos"
            />
            <span class="search-input-key-hint">/</span>
          </span>
        {/if}
        <button
          class="btn btn-ghost"
          type="button"
          disabled={syncing}
          onclick={() => sync()}
          title="Sync calendars and todos (R)"
        >
          {syncing ? 'Syncing…' : 'Sync'}
          <span class="key-hint">R</span>
        </button>
      </div>
      <div class="content-scroll flex flex-col flex-1 min-h-0 overflow-auto">
        <div class="calendar-height-wrapper min-h-0" style="--calendar-height-ratio: {app.calendarHeightRatio}">
          <Calendar
      events={events}
      todos={todos}
      loadingTodoId={togglingTodoId}
      searchQuery={app.searchQuery}
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
    </div>
  {:else}
    <div class="flex flex-1 flex-col min-h-0">
      <div class="subtoolbar flex flex-wrap items-center gap-3 px-4 py-3 shrink-0">
        {#if loading}
          <span class="text-sm text-[var(--text-muted)]" role="status" aria-live="polite">Loading…</span>
        {/if}
        <button
          type="button"
          class="btn btn-ghost text-sm inline-flex items-baseline gap-1.5"
          onclick={() => app.toggleShowCompletedTodos()}
          title="Toggle show completed todos (S)"
        >
          {app.showCompletedTodos ? 'Hide completed' : 'Show completed'}
          <span class="key-hint">S</span>
        </button>
        <div class="dropdown-box">
          <span class="dropdown-box-label">Order</span>
          <select
            value={app.todoOrder}
            onchange={(e) => app.setTodoOrder((e.currentTarget as HTMLSelectElement).value as 'oldest' | 'newest')}
          >
            <option value="oldest">Oldest first</option>
            <option value="newest">Newest first</option>
          </select>
        </div>
        <span class="text-xs text-[var(--text-muted)]" title="Total and completed count in current data">
          ({todos.length} total, {todos.filter((t) => t.completed).length} completed)
        </span>
        <span class="search-input-wrap">
          <input
            id="calslop-search-input"
            type="search"
            class="search-input"
            placeholder="Search todos…"
            value={app.searchInputValue}
            oninput={(e) => app.setSearchInputValue((e.currentTarget as HTMLInputElement).value)}
            onkeydown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                app.applySearch();
                (e.currentTarget as HTMLInputElement).blur();
              }
              if (e.key === 'Escape') {
                e.preventDefault();
                app.clearSearch();
                (e.currentTarget as HTMLInputElement).blur();
              }
            }}
            title="Search todos (/ to focus, Enter to filter, Escape to exit search)"
            aria-label="Search todos"
          />
          <span class="search-input-key-hint">/</span>
        </span>
        <button
          class="btn btn-ghost ml-auto"
          type="button"
          disabled={syncing}
          onclick={() => sync()}
          title="Sync calendars and todos (R)"
        >
          {syncing ? 'Syncing…' : 'Sync'}
          <span class="key-hint">R</span>
        </button>
      </div>
      <div class="content-scroll flex-1 min-h-0 overflow-auto">
        <TodoList
          todos={todos}
          showCompleted={app.showCompletedTodos}
          todoOrder={app.todoOrder}
          searchQuery={app.searchQuery}
          loadingTodoId={togglingTodoId}
          onToggle={handleToggleTodo}
          onSelect={handleSelectTodo}
          showToolbar={false}
        />
      </div>
    </div>
  {/if}
</div>

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
