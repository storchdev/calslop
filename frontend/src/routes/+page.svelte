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
  import { getEvents, getTodos, pushTodosByDateRange, updateTodo } from '$lib/api';
  import type { Event, Todo } from '$lib/types';
  import { parseUtcIfNeeded } from '$lib/date';

  let { data }: PageProps = $props();
  let events = $state<Event[]>([]);
  let todos = $state<Todo[]>([]);
  let loading = $state(false);
  let syncing = $state(false);
  let notificationError = $state('');
  let selectedTodo = $state<Todo | null>(null);
  let selectedEvent = $state<Event | null>(null);
  let cacheReady = $state(false);

  const CACHE_KEY = 'calslop-home-cache-v1';
  const notifiedAlerts = new Set<string>();
  const ALERT_LATE_GRACE_MS = 15_000;
  let lastNotificationCheckMs = Date.now();

  type ArmedAlert = {
    key: string;
    kind: 'event' | 'todo';
    title: string;
    iso: string;
    minutes: number;
    alertAtMs: number;
    ongoingUntilMs: number | null;
  };
  let armedAlerts = $state<ArmedAlert[]>([]);

  function rebuildArmedAlerts() {
    const now = Date.now();
    const next: ArmedAlert[] = [];

    for (const ev of events) {
      if (ev.cancelled || !ev.alert_minutes_before?.length) continue;
      const startMs = parseUtcIfNeeded(ev.start).getTime();
      const endMs = parseUtcIfNeeded(ev.end).getTime();
      if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) continue;

      for (const rawMinutes of ev.alert_minutes_before) {
        const minutes = Number(rawMinutes);
        if (!Number.isFinite(minutes) || minutes < 0) continue;
        const alertAtMs = startMs - minutes * 60_000;

        // Keep only alerts that can still fire:
        // - future reminder alerts
        // - at-time event reminders when event is still active (for refresh behavior)
        if (minutes === 0) {
          if (endMs <= now) continue;
        } else if (alertAtMs <= now) {
          continue;
        }

        next.push({
          key: `event:${ev.id}:${ev.start}:${minutes}`,
          kind: 'event',
          title: ev.title || 'Event reminder',
          iso: ev.start,
          minutes,
          alertAtMs,
          ongoingUntilMs: minutes === 0 ? endMs : null,
        });
      }
    }

    for (const todo of todos) {
      if (todo.completed || !todo.due || !todo.alert_minutes_before?.length) continue;
      const dueMs = parseUtcIfNeeded(todo.due).getTime();
      if (!Number.isFinite(dueMs)) continue;

      for (const rawMinutes of todo.alert_minutes_before) {
        const minutes = Number(rawMinutes);
        if (!Number.isFinite(minutes) || minutes < 0) continue;
        const alertAtMs = dueMs - minutes * 60_000;
        if (alertAtMs <= now) continue;

        next.push({
          key: `todo:${todo.id}:${todo.due}:${minutes}`,
          kind: 'todo',
          title: todo.summary || 'Todo reminder',
          iso: todo.due,
          minutes,
          alertAtMs,
          ongoingUntilMs: null,
        });
      }
    }

    next.sort((a, b) => a.alertAtMs - b.alertAtMs);
    armedAlerts = next;

    // Keep dedupe set in sync with active alert keys.
    const keys = new Set(next.map((a) => a.key));
    for (const k of Array.from(notifiedAlerts)) {
      if (!keys.has(k)) notifiedAlerts.delete(k);
    }
  }

  function readCachedData(): { events: Event[]; todos: Todo[] } | null {
    if (typeof localStorage === 'undefined') return null;
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as { events?: Event[]; todos?: Todo[] };
      if (!Array.isArray(parsed.events) || !Array.isArray(parsed.todos)) return null;
      return { events: parsed.events, todos: parsed.todos };
    } catch {
      return null;
    }
  }

  function writeCachedData(nextEvents: Event[], nextTodos: Todo[]) {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ events: nextEvents, todos: nextTodos }));
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
    writeCachedData(events, todos);
  });

  $effect(() => {
    events;
    todos;
    rebuildArmedAlerts();
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
    const cached = readCachedData();
    if (cached) {
      events = cached.events;
      todos = cached.todos;
    }
    cacheReady = true;
    refresh();
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
    if (app.desktopNotificationsEnabled) {
      app.setDesktopNotificationsEnabled(false);
      lastNotificationCheckMs = Date.now();
      return;
    }
    if (typeof window === 'undefined' || !('Notification' in window)) {
      notificationError = 'Desktop notifications are not supported in this browser.';
      return;
    }
    if (Notification.permission === 'default') {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        notificationError = 'Notification permission was not granted.';
        return;
      }
    }
    if (Notification.permission !== 'granted') {
      notificationError = 'Enable notification permission in your browser settings first.';
      return;
    }
    app.setDesktopNotificationsEnabled(true);
    lastNotificationCheckMs = Date.now();
    try {
      new Notification('Notifications enabled', { body: 'Calslop reminders are active.' });
    } catch {
    }
    checkDueNotifications();
  }

  function formatNotificationTime(iso: string): string {
    return parseUtcIfNeeded(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  }

  function checkDueNotifications() {
    if (typeof window === 'undefined' || !('Notification' in window)) return;
    if (!app.desktopNotificationsEnabled || Notification.permission !== 'granted') return;
    const now = Date.now();
    const since = lastNotificationCheckMs;
    lastNotificationCheckMs = now;

    const remaining: ArmedAlert[] = [];
    for (const alert of armedAlerts) {
      const isOngoingAtTimeEvent =
        alert.kind === 'event' &&
        alert.minutes === 0 &&
        now >= alert.alertAtMs &&
        alert.ongoingUntilMs !== null &&
        now < alert.ongoingUntilMs;

      const isFresh = now - alert.alertAtMs <= ALERT_LATE_GRACE_MS;
      const isDueNow = alert.alertAtMs <= now && alert.alertAtMs > since && isFresh;
      const shouldNotify = isOngoingAtTimeEvent || isDueNow;

      if (shouldNotify && !notifiedAlerts.has(alert.key)) {
        notifiedAlerts.add(alert.key);
        const body = alert.minutes > 0
          ? `${formatNotificationTime(alert.iso)} (${alert.minutes}m before)`
          : formatNotificationTime(alert.iso);
        try {
          new Notification(alert.title, { body });
        } catch {
          // Ignore per-notification errors and continue checking others.
        }
      }

      if (isOngoingAtTimeEvent || alert.alertAtMs > now) {
        remaining.push(alert);
      }
    }

    if (remaining.length !== armedAlerts.length) {
      armedAlerts = remaining;
    }
  }

  $effect(() => {
    if (typeof window === 'undefined') return;
    if (!app.desktopNotificationsEnabled) return;
    checkDueNotifications();
    const interval = window.setInterval(checkDueNotifications, 1_000);
    return () => window.clearInterval(interval);
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
      const d = new Date(saved.start);
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
    onclose={closeEventModal}
    onsave={handleEventSave}
  />
{:else if app.modalOpen === 'todo'}
  <TodoModal
    todoId={app.editingId}
    initialTodo={selectedTodo}
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
