<script lang="ts">
  import { onMount } from 'svelte';
  import type { PageProps } from './$types';
  import { app } from '$lib/stores/app.svelte';
  import Calendar from '$lib/components/Calendar.svelte';
  import TodoList from '$lib/components/TodoList.svelte';
  import EventModal from '$lib/components/EventModal.svelte';
  import TodoModal from '$lib/components/TodoModal.svelte';
  import PushOffModal from '$lib/components/PushOffModal.svelte';
  import ShortcutsModal from '$lib/components/ShortcutsModal.svelte';
  import {
    getEvents,
    getNotificationSettings,
    getSources,
    getTodos,
    pushTodosByDateRange,
    updateNotificationSettings,
    updateTodo,
  } from '$lib/api';
  import type { Event, Todo, Source } from '$lib/types';
  import { parseUtcIfNeeded } from '$lib/date';
  import { sourceColorMap } from '$lib/source-colors';

  let { data }: PageProps = $props();
  let events = $state<Event[]>([]);
  let todos = $state<Todo[]>([]);
  let loading = $state(false);
  let syncing = $state(false);
  let notificationError = $state('');
  let selectedTodo = $state<Todo | null>(null);
  let selectedEvent = $state<Event | null>(null);
  let sourceColors = $state<Record<string, string>>({});
  let sources = $state<Source[]>([]);
  let selectedTodoSource = $state('all');
  let cacheReady = $state(false);
  let loadedEventStartMs = $state<number | null>(null);
  let loadedEventEndMs = $state<number | null>(null);
  let eventRangeFetchInFlight = $state(false);
  let fullRefreshInFlight = $state(false);

  const EVENT_PRELOAD_MONTHS = 6;
  const EVENT_PREFETCH_EDGE_MONTHS = 2;

  const CACHE_KEY = 'calslop-home-cache-v2';

  type CachedHomeData = {
    events?: Event[];
    todos?: Todo[];
    loadedEventStartMs?: number | null;
    loadedEventEndMs?: number | null;
  };

  function readCachedData(): {
    events: Event[];
    todos: Todo[];
    loadedEventStartMs: number | null;
    loadedEventEndMs: number | null;
  } | null {
    if (typeof localStorage === 'undefined') return null;
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as CachedHomeData;
      if (!Array.isArray(parsed.events) || !Array.isArray(parsed.todos)) return null;
      const startMs = typeof parsed.loadedEventStartMs === 'number' && Number.isFinite(parsed.loadedEventStartMs)
        ? parsed.loadedEventStartMs
        : null;
      const endMs = typeof parsed.loadedEventEndMs === 'number' && Number.isFinite(parsed.loadedEventEndMs)
        ? parsed.loadedEventEndMs
        : null;
      return {
        events: parsed.events,
        todos: parsed.todos,
        loadedEventStartMs: startMs,
        loadedEventEndMs: endMs,
      };
    } catch {
      return null;
    }
  }

  function writeCachedData(
    nextEvents: Event[],
    nextTodos: Todo[],
    nextLoadedEventStartMs: number | null,
    nextLoadedEventEndMs: number | null,
  ) {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        events: nextEvents,
        todos: nextTodos,
        loadedEventStartMs: nextLoadedEventStartMs,
        loadedEventEndMs: nextLoadedEventEndMs,
      }));
    } catch {
      // ignore quota/storage errors
    }
  }

  $effect(() => {
    if (data?.events) events = data.events;
    if (data?.todos) todos = data.todos;
  });

  $effect(() => {
    if (!cacheReady) return;
    writeCachedData(events, todos, loadedEventStartMs, loadedEventEndMs);
  });

  function monthStart(date: Date): Date {
    return new Date(date.getFullYear(), date.getMonth(), 1);
  }

  function monthEnd(date: Date): Date {
    return new Date(date.getFullYear(), date.getMonth() + 1, 0);
  }

  function monthIndex(date: Date): number {
    return date.getFullYear() * 12 + date.getMonth();
  }

  function toIso(ms: number): string {
    return new Date(ms).toISOString();
  }

  function computeTargetWindow(selectedDate: Date): { startMs: number; endMs: number } {
    const startMs = monthStart(new Date(selectedDate.getFullYear(), selectedDate.getMonth() - EVENT_PRELOAD_MONTHS, 1)).getTime();
    const endMs = monthEnd(new Date(selectedDate.getFullYear(), selectedDate.getMonth() + EVENT_PRELOAD_MONTHS, 1)).getTime();
    return { startMs, endMs };
  }

  function setLoadedEventRange(startMs: number, endMs: number) {
    loadedEventStartMs = startMs;
    loadedEventEndMs = endMs;
  }

  async function fetchEventsOnly(startIso: string, endIso: string): Promise<Event[]> {
    return getEvents(startIso, endIso);
  }

  function mergeEventsById(existing: Event[], incoming: Event[]): Event[] {
    const byId = new Map(existing.map((event) => [event.id, event]));
    for (const event of incoming) byId.set(event.id, event);
    return [...byId.values()];
  }

  function shouldPrefetchForDate(selectedDate: Date): boolean {
    if (loadedEventStartMs == null || loadedEventEndMs == null) return true;
    const selectedMonth = monthIndex(selectedDate);
    const startMonth = monthIndex(new Date(loadedEventStartMs));
    const endMonth = monthIndex(new Date(loadedEventEndMs));
    if (selectedMonth < startMonth || selectedMonth > endMonth) return true;
    return selectedMonth - startMonth <= EVENT_PREFETCH_EDGE_MONTHS
      || endMonth - selectedMonth <= EVENT_PREFETCH_EDGE_MONTHS;
  }

  async function ensureEventWindowForDate(selectedDate: Date) {
    if (eventRangeFetchInFlight || fullRefreshInFlight) return;
    if (!shouldPrefetchForDate(selectedDate)) return;

    const target = computeTargetWindow(selectedDate);
    if (loadedEventStartMs == null || loadedEventEndMs == null) {
      eventRangeFetchInFlight = true;
      try {
        const fetched = await fetchEventsOnly(toIso(target.startMs), toIso(target.endMs));
        events = mergeEventsById(events, fetched);
        setLoadedEventRange(target.startMs, target.endMs);
      } finally {
        eventRangeFetchInFlight = false;
      }
      return;
    }

    const currentStart = loadedEventStartMs;
    const currentEnd = loadedEventEndMs;
    const missingLeft = target.startMs < currentStart;
    const missingRight = target.endMs > currentEnd;
    if (!missingLeft && !missingRight) return;

    eventRangeFetchInFlight = true;
    try {
      const requests: Array<Promise<Event[]>> = [];
      if (missingLeft) {
        requests.push(fetchEventsOnly(toIso(target.startMs), toIso(currentStart)));
      }
      if (missingRight) {
        requests.push(fetchEventsOnly(toIso(currentEnd), toIso(target.endMs)));
      }
      const fetchedBatches = await Promise.all(requests);
      for (const fetched of fetchedBatches) {
        events = mergeEventsById(events, fetched);
      }
      setLoadedEventRange(
        missingLeft ? target.startMs : currentStart,
        missingRight ? target.endMs : currentEnd,
      );
    } finally {
      eventRangeFetchInFlight = false;
    }
  }

  /** Full sync for events, todos, and sources. Used for sync + post-mutation consistency. */
  async function refresh() {
    const hasData = events.length > 0 || todos.length > 0;
    if (!hasData) loading = true;
    fullRefreshInFlight = true;
    eventRangeFetchInFlight = true;
    try {
      const { startMs, endMs } = computeTargetWindow(app.selectedDate);
      const start = toIso(startMs);
      const end = toIso(endMs);
      const [e, t, s] = await Promise.all([getEvents(start, end), getTodos(), getSources()]);
      events = e;
      todos = t;
      sources = s;
      sourceColors = sourceColorMap(s);
      setLoadedEventRange(startMs, endMs);
      app.setUnsyncedChanges(false);
    } finally {
      fullRefreshInFlight = false;
      eventRangeFetchInFlight = false;
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

  function autoSyncMs(interval: string): number {
    switch (interval) {
      case '30s': return 30_000;
      case '1m': return 60_000;
      case '5m': return 300_000;
      default: return 0;
    }
  }

  function baseSourceId(sourceId: string): string {
    return sourceId.split('::')[0] || sourceId;
  }

  const sourceFilteredTodos = $derived(
    selectedTodoSource === 'all'
      ? todos
      : todos.filter((todo) => baseSourceId(todo.source_id) === selectedTodoSource)
  );

  const existingTodoCategories = $derived.by(() => {
    const seen = new Set<string>();
    const categories: string[] = [];
    for (const todo of todos) {
      for (const category of todo.categories ?? []) {
        const normalized = category.trim();
        if (!normalized) continue;
        const key = normalized.toLocaleLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        categories.push(normalized);
      }
    }
    return categories.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
  });

  onMount(() => {
    const cached = readCachedData();
    if (cached) {
      events = cached.events;
      todos = cached.todos;
      loadedEventStartMs = cached.loadedEventStartMs;
      loadedEventEndMs = cached.loadedEventEndMs;
    }
    cacheReady = true;
    refresh();
    void syncNotificationEnabledState();
    function onToggleDayTodo(ev: CustomEvent<{ todoId: string }>) {
      const todo = todos.find((t) => t.id === ev.detail.todoId);
      if (todo) handleToggleTodo(todo);
    }
    function onSync() {
      sync();
    }
    function onToggleDesktopNotifications() {
      void toggleDesktopNotifications();
    }
    window.addEventListener('calslop-toggle-day-todo', onToggleDayTodo as EventListener);
    window.addEventListener('calslop-sync', onSync);
    window.addEventListener('calslop-toggle-desktop-notifications', onToggleDesktopNotifications);
    return () => {
      window.removeEventListener('calslop-toggle-day-todo', onToggleDayTodo as EventListener);
      window.removeEventListener('calslop-sync', onSync);
      window.removeEventListener('calslop-toggle-desktop-notifications', onToggleDesktopNotifications);
    };
  });

  async function toggleDesktopNotifications() {
    notificationError = '';
    try {
      const settings = await updateNotificationSettings({ enabled: !app.desktopNotificationsEnabled });
      app.setDesktopNotificationsEnabled(settings.enabled);
      notificationError = settings.health_error ?? '';
    } catch (e) {
      notificationError = e instanceof Error ? e.message : 'Failed to update notification settings.';
    }
  }

  async function syncNotificationEnabledState() {
    notificationError = '';
    try {
      const settings = await getNotificationSettings();
      app.setDesktopNotificationsEnabled(settings.enabled);
      notificationError = settings.health_error ?? '';
    } catch (e) {
      notificationError = e instanceof Error ? e.message : 'Failed to load notification settings.';
    }
  }

  $effect(() => {
    if (typeof window === 'undefined') return;
    void ensureEventWindowForDate(app.selectedDate);
  });

  $effect(() => {
    if (typeof window === 'undefined') return;
    const ms = autoSyncMs(app.autoSyncInterval);
    if (ms <= 0) return;
    const id = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      void sync();
    }, ms);
    return () => window.clearInterval(id);
  });

  let togglingTodoId = $state<string | null>(null);
  let pendingCreatedEventFocus = $state<{ id: string; start: string; title: string } | null>(null);

  function isSameLocalDay(a: Date, b: Date): boolean {
    return (
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate()
    );
  }

  async function handleEventSave(saved?: { id: string; start: string; title: string }) {
    const shouldFocusCreated =
      app.viewMode === 'calendar' &&
      app.calendarView === 'day' &&
      !!saved;

    if (shouldFocusCreated && saved) {
      const d = parseUtcIfNeeded(saved.start);
      const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
      if (!isSameLocalDay(target, app.selectedDate)) {
        app.setSelectedDate(target);
      }
    }

    await refresh();

    if (shouldFocusCreated && saved) {
      pendingCreatedEventFocus = saved;
    }
  }

  function closeEventModal() {
    app.setModalOpen(null);
    app.setEditingId(null);
    selectedEvent = null;
  }

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

  async function handleTodoSave() {
    await refresh();
    selectedTodo = null;
  }

  async function handlePushOffApply(startIso: string | null, endIso: string | null, days: number, overdueOnly: boolean) {
    const result = await pushTodosByDateRange(startIso, endIso, days, overdueOnly);
    if (result.failed.length > 0) {
      throw new Error(`Updated ${result.updated} todos, but ${result.failed.length} failed.`);
    }
    await refresh();
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
          <span class="dropdown-box-label">Notifications</span>
          <label class="option-box-content inline-flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={app.desktopNotificationsEnabled} onchange={() => void toggleDesktopNotifications()} />
            <span class="key-hint">O</span>
          </label>
        </div>
        {#if notificationError}
          <span class="text-xs text-red-600">{notificationError}</span>
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
            sourceColors={sourceColors}
            loadingTodoId={togglingTodoId}
            focusEventRequest={pendingCreatedEventFocus}
            onFocusEventRequestHandled={() => {
              pendingCreatedEventFocus = null;
            }}
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
        <div class="dropdown-box">
          <span class="dropdown-box-label">Source</span>
          <select bind:value={selectedTodoSource}>
            <option value="all">All sources</option>
            {#each sources as source}
              <option value={source.id}>{source.name}</option>
            {/each}
          </select>
        </div>
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
          class="btn btn-ghost inline-flex items-baseline gap-1.5"
          type="button"
          onclick={() => app.setModalOpen('pushOff')}
          title="Push todos by due range (P)"
        >
          Push off
          <span class="key-hint">P</span>
        </button>
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
      <div class="content-scroll flex-1 min-h-0 overflow-auto">
        <TodoList
          todos={sourceFilteredTodos}
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
    onclose={closeEventModal}
    onsave={handleEventSave}
  />
{:else if app.modalOpen === 'todo'}
  <TodoModal
    todoId={app.editingId}
    initialTodo={selectedTodo}
    existingCategories={existingTodoCategories}
    onclose={() => { app.setModalOpen(null); app.setEditingId(null); selectedTodo = null; }}
    onsave={handleTodoSave}
  />
{:else if app.modalOpen === 'shortcuts'}
  <ShortcutsModal onclose={() => app.setModalOpen(null)} />
{:else if app.modalOpen === 'pushOff'}
  <PushOffModal
    onclose={() => app.setModalOpen(null)}
    onapply={handlePushOffApply}
  />
{/if}
