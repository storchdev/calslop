<script lang="ts">
  import { tick } from 'svelte';
  import type { Event, Todo } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { formatInTimezone, parseUtcIfNeeded } from '$lib/date';

  interface Props {
    events: Event[];
    todos?: Todo[];
    selectedDate: Date;
    searchQuery?: string;
    onSelectDay?: (d: Date) => void;
    onSelectEvent?: (ev: Event) => void;
    onSelectTodo?: (todo: Todo) => void;
  }

  let { events, todos = [], selectedDate, searchQuery = '', onSelectDay, onSelectEvent, onSelectTodo }: Props = $props();

  function matchesSearchEvent(ev: Event, q: string): boolean {
    if (!q) return false;
    const lower = q.toLowerCase();
    return (
      ev.title.toLowerCase().includes(lower) ||
      (ev.description?.toLowerCase().includes(lower) ?? false)
    );
  }
  function matchesSearchTodo(todo: Todo, q: string): boolean {
    if (!q) return false;
    const lower = q.toLowerCase();
    return (
      todo.summary.toLowerCase().includes(lower) ||
      (todo.description?.toLowerCase().includes(lower) ?? false)
    );
  }
  function dayMatchesSearch(d: Date, q: string): boolean {
    if (!q.trim()) return false;
    const evs = eventsForDay(d);
    const tds = todosForDay(d);
    return evs.some((e) => matchesSearchEvent(e, q)) || tds.some((t) => matchesSearchTodo(t, q));
  }

  const density = $derived(app.calendarDensity);
  const showTodos = $derived(app.showTodosOnCalendar);

  const monthStart = $derived(new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1));
  const monthEnd = $derived(new Date(selectedDate.getFullYear(), selectedDate.getMonth() + 1, 0));
  const startPad = $derived(monthStart.getDay()); // Sunday first
  const daysInMonth = $derived(monthEnd.getDate());
  const totalCells = $derived(startPad + daysInMonth);
  const weeks = $derived(Math.ceil(totalCells / 7));

  function dateForCell(cellIndex: number): Date | null {
    const day = cellIndex - startPad + 1;
    if (day < 1 || day > daysInMonth) return null;
    return new Date(selectedDate.getFullYear(), selectedDate.getMonth(), day);
  }

  function isToday(d: Date) {
    const t = new Date();
    return d.getDate() === t.getDate() && d.getMonth() === t.getMonth() && d.getFullYear() === t.getFullYear();
  }

  function isSelected(d: Date) {
    return (
      d.getDate() === selectedDate.getDate() &&
      d.getMonth() === selectedDate.getMonth() &&
      d.getFullYear() === selectedDate.getFullYear()
    );
  }

  function eventsForDay(d: Date): Event[] {
    const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const dayEnd = dayStart + 24 * 60 * 60 * 1000;
    return events.filter((e) => {
      const start = new Date(e.start).getTime();
      const end = new Date(e.end).getTime();
      return start < dayEnd && end > dayStart;
    });
  }

  function todosForDay(d: Date): Todo[] {
    return todos.filter((t) => {
      if (!t.due) return false;
      const due = parseUtcIfNeeded(t.due);
      return due.getDate() === d.getDate() && due.getMonth() === d.getMonth() && due.getFullYear() === d.getFullYear();
    });
  }

  const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  // When switching to month view, sync focused day to selected date so Enter works without re-focusing a cell
  $effect(() => {
    if (app.calendarView !== 'month') return;
    const d = selectedDate;
    const idx = startPad + d.getDate() - 1;
    app.setFocusedDayDate(d);
    app.setFocusedDayIndex(idx);
  });

  // Update highlighted day indices for search mode (N / Shift+N navigation)
  $effect(() => {
    if (app.calendarView !== 'month' || !searchQuery.trim()) {
      app.setHighlightedDayIndices([]);
      return;
    }
    const indices: number[] = [];
    const total = weeks * 7;
    for (let i = 0; i < total; i++) {
      const d = dateForCell(i);
      if (d && dayMatchesSearch(d, searchQuery)) indices.push(i);
    }
    app.setHighlightedDayIndices(indices);
  });

  const MIN_BLOCK_HEIGHT = 24;
  /** Day view: height of each hour row, scaled by user's height ratio (0.5–2). */
  const rowHeight = $derived(60 * app.calendarHeightRatio);

  const dayStartMs = $derived(
    new Date(selectedDate.getFullYear(), selectedDate.getMonth(), selectedDate.getDate()).getTime()
  );
  const dayEndMs = $derived(dayStartMs + 24 * 60 * 60 * 1000);

  const dayEventsAll = $derived(
    events.filter((e) => {
      const start = parseUtcIfNeeded(e.start).getTime();
      const end = parseUtcIfNeeded(e.end).getTime();
      return start < dayEndMs && end > dayStartMs;
    })
  );
  const dayTodosAll = $derived(showTodos ? todosForDay(selectedDate) : []);

  const allDayEvents = $derived(dayEventsAll.filter((e) => e.all_day));
  const timedEvents = $derived(
    dayEventsAll
      .filter((e) => !e.all_day)
      .map((e) => {
        const startMs = parseUtcIfNeeded(e.start).getTime();
        const endMs = parseUtcIfNeeded(e.end).getTime();
        const startMin = Math.max(0, (startMs - dayStartMs) / 60000);
        const endMin = Math.min(24 * 60, (endMs - dayStartMs) / 60000);
        return { type: 'event' as const, event: e, startMin, endMin };
      })
  );

  function isDueAtMidnight(iso: string): boolean {
    const d = parseUtcIfNeeded(iso);
    return d.getUTCHours() === 0 && d.getUTCMinutes() === 0;
  }

  const allDayTodos = $derived(dayTodosAll.filter((t) => t.due && isDueAtMidnight(t.due)));
  const timedTodos = $derived(
    dayTodosAll
      .filter((t) => t.due && !isDueAtMidnight(t.due))
      .map((t) => {
        const dueMs = parseUtcIfNeeded(t.due!).getTime();
        const startMin = (dueMs - dayStartMs) / 60000;
        const endMin = Math.min(24 * 60, startMin + 0.25);
        return { type: 'todo' as const, todo: t, startMin, endMin };
      })
  );

  const allDayItems = $derived([
    ...allDayEvents.map((e) => ({ type: 'event' as const, event: e })),
    ...allDayTodos.map((t) => ({ type: 'todo' as const, todo: t })),
  ]);
  const timedItemsSorted = $derived(
    [...timedEvents, ...timedTodos].sort((a, b) => a.startMin - b.startMin)
  );
  const dayItems = $derived([...allDayItems, ...timedItemsSorted]);

  // Day view: keep focused item index in range; set to 0 when there are items and index was invalid
  $effect(() => {
    if (app.calendarView !== 'day') return;
    if (dayItems.length === 0) {
      app.setFocusedEventIndex(-1);
      return;
    }
    if (app.focusedEventIndex < 0 || app.focusedEventIndex >= dayItems.length) {
      app.setFocusedEventIndex(0);
    }
  });

  // Current time line: update every minute when viewing today
  let now = $state(new Date());
  $effect(() => {
    if (app.calendarView !== 'day' || !isToday(selectedDate)) return;
    const id = setInterval(() => {
      now = new Date();
    }, 60_000);
    return () => clearInterval(id);
  });
  const currentTimeTopPx = $derived.by(() => {
    if (!isToday(selectedDate)) return null;
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const minutesFromMidnight = (now.getTime() - startOfDay) / 60000;
    return (minutesFromMidnight / 60) * rowHeight;
  });

  // Scroll so the selected day is fully visible
  let calendarEl: HTMLDivElement | undefined;
  $effect(() => {
    const view = app.calendarView;
    const date = selectedDate;
    if (!calendarEl) return;
    tick().then(() => {
      const scrollParent = calendarEl?.closest('.content-scroll') as HTMLElement | null;
      if (!scrollParent) return;
      if (view === 'month') {
        const sel = calendarEl?.querySelector('.day-cell.selected') as HTMLElement | null;
        if (sel) sel.scrollIntoView({ block: 'nearest', behavior: 'smooth', inline: 'nearest' });
      } else if (view === 'day') {
        const nowLine = calendarEl?.querySelector('.day-view-now-line') as HTMLElement | null;
        if (nowLine) nowLine.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }
    });
  });
</script>

<div id="calendar-view" class="p-4 flex-1 min-h-0 flex flex-col" style="--calendar-height-ratio: {app.calendarHeightRatio}" role="application" aria-label="Calendar" bind:this={calendarEl}>
  {#if app.calendarView === 'month'}
    <div class="flex flex-1 min-h-0 flex-col">
      <h2 class="text-xl font-semibold mb-3 text-[var(--text)] shrink-0">
        {selectedDate.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
      </h2>
      <div class="grid grid-cols-7 gap-1 mb-1 text-xs text-[var(--text-muted)] shrink-0">
        {#each dayLabels as label}
          <span>{label}</span>
        {/each}
      </div>
      <div
        class="grid grid-cols-7 gap-1 flex-1 min-h-0"
        style="grid-template-rows: repeat({weeks}, 1fr);"
        role="grid"
      >
        {#each Array(weeks * 7) as _, i}
          {@const d = dateForCell(i)}
          {#if d}
            <button
              type="button"
              class="day-cell"
              class:today={isToday(d)}
              class:selected={isSelected(d)}
              class:search-match={searchQuery.trim() !== '' && dayMatchesSearch(d, searchQuery)}
              tabindex={app.focusedDayIndex === i ? 0 : -1}
              data-day-index={i}
              onfocus={() => {
                app.setFocusedDayIndex(i);
                app.setFocusedDayDate(d);
              }}
              onclick={() => {
                app.setSelectedDate(d);
                app.setFocusedDayDate(d);
                onSelectDay?.(d);
              }}
              onkeydown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  app.setSelectedDate(d);
                  app.setCalendarView('day');
                  onSelectDay?.(d);
                  return;
                }
                if (e.key === 'ArrowRight' && i + 1 < weeks * 7) {
                  app.setFocusedDayIndex(i + 1);
                  (e.currentTarget.nextElementSibling as HTMLElement)?.focus();
                }
                if (e.key === 'ArrowLeft' && i > 0) {
                  app.setFocusedDayIndex(i - 1);
                  (e.currentTarget.previousElementSibling as HTMLElement)?.focus();
                }
                if (e.key === 'ArrowDown' && i + 7 < weeks * 7) {
                  app.setFocusedDayIndex(i + 7);
                  const row = Math.floor(i / 7);
                  const next = (row + 1) * 7 + (i % 7);
                  document.querySelector(`[data-day-index="${next}"]`)?.focus();
                }
                if (e.key === 'ArrowUp' && i >= 7) {
                  app.setFocusedDayIndex(i - 7);
                  document.querySelector(`[data-day-index="${i - 7}"]`)?.focus();
                }
              }}
            >
              {#if density === 'minimal'}
                <span class="day-num-centered block text-2xl font-semibold">{d.getDate()}</span>
              {:else if density === 'dense'}
                {@const evs = eventsForDay(d)}
                {@const tds = showTodos ? todosForDay(d) : []}
                {@const combined = [...evs.map((e) => ({ kind: 'event' as const, event: e })), ...tds.map((todo) => ({ kind: 'todo' as const, todo }))].sort((a, b) => {
                  const at = a.kind === 'event' ? new Date(a.event.start).getTime() : new Date(a.todo.due ?? 0).getTime();
                  const bt = b.kind === 'event' ? new Date(b.event.start).getTime() : new Date(b.todo.due ?? 0).getTime();
                  return at - bt;
                }).slice(0, 5)}
                <div class="dense-day-inner flex flex-row items-baseline gap-1.5 absolute inset-1 overflow-hidden text-left">
                  <span class="font-semibold text-sm shrink-0 leading-none">{d.getDate()}</span>
                  <div class="flex-1 min-w-0 overflow-hidden flex flex-col gap-0.5">
                    {#each combined as item}
                      {#if item.kind === 'event'}
                        <div class="text-[0.65rem] overflow-hidden text-ellipsis whitespace-nowrap leading-none" class:line-through={item.event.cancelled} title={item.event.title}>
                          {item.event.all_day ? '' : formatInTimezone(item.event.start, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)} {item.event.title}
                        </div>
                      {:else}
                        <div class="text-[0.65rem] overflow-hidden text-ellipsis whitespace-nowrap flex items-center gap-0.5 leading-none italic text-[var(--text-muted)]" class:line-through={item.todo.completed} title={item.todo.summary} onclick={(e) => { e.preventDefault(); e.stopPropagation(); onSelectTodo?.(item.todo); }}>
                          <span class="min-w-0 truncate">{item.todo.due ? formatInTimezone(item.todo.due, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined) : '–'} {item.todo.summary}</span>
                          {#if item.todo.completed}
                            <span class="opacity-80 shrink-0" aria-hidden="true">✓</span>
                          {/if}
                        </div>
                      {/if}
                    {/each}
                  </div>
                </div>
              {:else}
                <!-- balanced: events and todos combined, centered; (+N) only when truncated -->
                {@const evs = eventsForDay(d)}
                {@const tds = showTodos ? todosForDay(d) : []}
                {@const combined = [...evs.map((e) => ({ kind: 'event' as const, event: e })), ...tds.map((t) => ({ kind: 'todo' as const, todo: t }))].sort((a, b) => {
                  const at = a.kind === 'event' ? new Date(a.event.start).getTime() : new Date(a.todo.due ?? 0).getTime();
                  const bt = b.kind === 'event' ? new Date(b.event.start).getTime() : new Date(b.todo.due ?? 0).getTime();
                  return at - bt;
                })}
                {@const visible = combined.slice(0, 2)}
                {@const hasMore = combined.length > 2}
                <span class="day-num-centered block font-semibold">{d.getDate()}</span>
                <div class="balanced-view-content">
                  {#each visible as item}
                    {#if item.kind === 'event'}
                      <span class="block text-[0.7rem] overflow-hidden text-ellipsis whitespace-nowrap text-center" class:line-through={item.event.cancelled} title={item.event.title}>{item.event.title}</span>
                    {:else}
                      <span class="block text-[0.7rem] overflow-hidden text-ellipsis whitespace-nowrap flex items-center justify-center gap-0.5 italic text-[var(--text-muted)]" class:line-through={item.todo.completed} title={item.todo.summary} onclick={(e) => { e.preventDefault(); e.stopPropagation(); onSelectTodo?.(item.todo); }}>
                        {#if item.todo.completed}
                          <span class="opacity-80 shrink-0" aria-hidden="true">✓</span>
                        {/if}
                        {item.todo.summary}
                      </span>
                    {/if}
                  {/each}
                  {#if hasMore}
                    <span class="block text-[0.7rem] overflow-hidden text-ellipsis whitespace-nowrap text-center text-[var(--text-muted)]">
                      +{combined.length - 2} more
                    </span>
                  {/if}
                </div>
              {/if}
            </button>
          {:else}
            <div class="day-cell min-h-[60px] bg-transparent border-none cursor-default"></div>
          {/if}
        {/each}
      </div>
    </div>
  {:else}
    <!-- Day view: 24h timeline -->
    <div class="day-view flex flex-col flex-1 min-h-0">
      <h3 class="day-view-title shrink-0 mb-2">{selectedDate.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</h3>

      {#if allDayItems.length > 0}
        <div class="day-view-allday shrink-0 mb-2">
          <span class="day-view-allday-label">All day</span>
          <div class="day-view-allday-items">
            {#each allDayItems as item, i}
              {#if item.type === 'event'}
                <button
                  type="button"
                  class="day-event day-event-block"
                  class:focused={app.focusedEventIndex === i}
                  class:line-through={item.event.cancelled}
                  tabindex={app.focusedEventIndex === i ? 0 : -1}
                  data-day-item-index={i}
                  onfocus={() => app.setFocusedEventIndex(i)}
                  onclick={() => onSelectEvent?.(item.event)}
                >
                  {item.event.title}
                </button>
              {:else}
                <button
                  type="button"
                  class="day-todo day-todo-block"
                  class:focused={app.focusedEventIndex === i}
                  class:completed={item.todo.completed}
                  tabindex={app.focusedEventIndex === i ? 0 : -1}
                  data-day-item-index={i}
                  data-day-item-todo-id={item.todo.id}
                  onfocus={() => app.setFocusedEventIndex(i)}
                  onclick={() => onSelectTodo?.(item.todo)}
                >
                  <span class="day-todo-checkbox" aria-hidden="true">
                    {#if item.todo.completed}✓{:else}<span class="checkbox-empty"></span>{/if}
                  </span>
                  <span class="day-todo-label">{item.todo.summary}</span>
                </button>
              {/if}
            {/each}
          </div>
        </div>
      {/if}

      <div class="day-view-timeline-wrap flex-1 min-h-0 flex flex-col" data-day-timeline-scroll>
        <div class="day-view-timeline" style="height: {24 * rowHeight}px;">
          {#if currentTimeTopPx != null && currentTimeTopPx >= 0 && currentTimeTopPx <= 24 * rowHeight}
            <div
              class="day-view-now-line"
              style="top: {currentTimeTopPx}px;"
              role="presentation"
              aria-hidden="true"
            ></div>
          {/if}
          {#each Array(24) as _, hour}
            <div class="day-view-hour" style="height: {rowHeight}px;">
              <span class="day-view-hour-label">
                {hour === 0 ? '12am' : hour < 12 ? `${hour}am` : hour === 12 ? '12pm' : `${hour - 12}pm`}
              </span>
            </div>
          {/each}

          {#each timedItemsSorted as item, idx}
            {@const i = allDayItems.length + idx}
            {@const topPx = item.startMin / 60 * rowHeight}
            {@const heightPx = Math.max(MIN_BLOCK_HEIGHT, (item.endMin - item.startMin) / 60 * rowHeight)}
            {#if item.type === 'event'}
              <button
                type="button"
                class="day-event day-event-timed"
                class:focused={app.focusedEventIndex === i}
                class:line-through={item.event.cancelled}
                tabindex={app.focusedEventIndex === i ? 0 : -1}
                data-day-item-index={i}
                style="top: {topPx}px; height: {heightPx}px;"
                onfocus={() => app.setFocusedEventIndex(i)}
                onclick={() => onSelectEvent?.(item.event)}
              >
                <span class="day-event-time">
                  {formatInTimezone(item.event.start, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)}
                  {#if item.event.end}
                    – {formatInTimezone(item.event.end, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)}
                  {/if}
                </span>
                <span class="day-event-title">{item.event.title}</span>
              </button>
            {:else}
              <button
                type="button"
                class="day-todo day-todo-timed"
                class:focused={app.focusedEventIndex === i}
                class:completed={item.todo.completed}
                tabindex={app.focusedEventIndex === i ? 0 : -1}
                data-day-item-index={i}
                data-day-item-todo-id={item.todo.id}
                style="top: {topPx}px; height: {heightPx}px;"
                onfocus={() => app.setFocusedEventIndex(i)}
                onclick={() => onSelectTodo?.(item.todo)}
              >
                <span class="day-todo-checkbox" aria-hidden="true">
                  {#if item.todo.completed}✓{:else}<span class="checkbox-empty"></span>{/if}
                </span>
                <span class="day-todo-time">
                  {formatInTimezone(item.todo.due ?? '', { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)}
                </span>
                <span class="day-todo-label">{item.todo.summary}</span>
              </button>
            {/if}
          {/each}
        </div>
      </div>

      {#if dayItems.length === 0}
        <p class="text-[var(--text-muted)] shrink-0 mt-2">No events or todos this day.</p>
      {/if}
    </div>
  {/if}
</div>
