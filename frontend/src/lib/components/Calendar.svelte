<script lang="ts">
  import { tick } from 'svelte';
  import type { Event, Todo } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { formatInTimezone, parseUtcIfNeeded } from '$lib/date';

  interface Props {
    events: Event[];
    todos?: Todo[];
    sourceColors?: Record<string, string>;
    loadingTodoId?: string | null;
    focusEventRequest?: { id: string; start: string; title: string } | null;
    onFocusEventRequestHandled?: () => void;
    selectedDate: Date;
    searchQuery?: string;
    onSelectDay?: (d: Date) => void;
    onSelectEvent?: (ev: Event) => void;
    onSelectTodo?: (todo: Todo) => void;
  }

  let {
    events,
    todos = [],
    sourceColors = {},
    loadingTodoId = null,
    focusEventRequest = null,
    onFocusEventRequestHandled,
    selectedDate,
    searchQuery = '',
    onSelectDay,
    onSelectEvent,
    onSelectTodo,
  }: Props = $props();

  function sourceColorStyle(sourceId: string): string {
    const baseSourceId = sourceId.split('::')[0] || sourceId;
    const color = sourceColors[sourceId] || sourceColors[baseSourceId];
    return color ? `--source-color: ${color};` : '';
  }

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
    const dayKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const dayEnd = dayStart + 24 * 60 * 60 * 1000;

    const getIsoDatePart = (iso: string): string | null => {
      const m = iso.match(/^(\d{4}-\d{2}-\d{2})/);
      return m ? m[1] : null;
    };

    return events.filter((e) => {
      if (e.all_day) {
        const startDate = getIsoDatePart(e.start);
        const endDate = getIsoDatePart(e.end);
        if (!startDate || !endDate) return false;
        return dayKey >= startDate && dayKey < endDate;
      }

      const start = parseUtcIfNeeded(e.start).getTime();
      const end = parseUtcIfNeeded(e.end).getTime();
      return Number.isFinite(start) && Number.isFinite(end) && start < dayEnd && end > dayStart;
    });
  }

  function todosForDay(d: Date): Todo[] {
    return todos.filter((t) => {
      if (!t.due) return false;
      const due = parseUtcIfNeeded(t.due);
      return due.getDate() === d.getDate() && due.getMonth() === d.getMonth() && due.getFullYear() === d.getFullYear();
    });
  }

  function isTodoOverdue(todo: Todo): boolean {
    if (todo.completed || !todo.due) return false;
    return parseUtcIfNeeded(todo.due).getTime() < Date.now();
  }

  function truncateDenseText(text: string, maxChars = 96): string {
    const normalized = text.trim();
    if (normalized.length <= maxChars) return normalized;
    return `${normalized.slice(0, maxChars - 1).trimEnd()}…`;
  }

  function normalizeLocationText(location: string | null | undefined): string | null {
    const normalized = location?.trim() ?? '';
    return normalized.length > 0 ? normalized : null;
  }

  const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  // Measure day cell height so we can show more/fewer events based on available space (dense + balanced)
  let dayCellHeightPx = $state(0);
  let monthGridEl = $state<HTMLDivElement | undefined>(undefined);
  let upcomingCols = $state(3);
  let upcomingGridEl = $state<HTMLDivElement | undefined>(undefined);
  $effect(() => {
    const el = monthGridEl;
    const w = weeks;
    if (!el || app.calendarView !== 'month' || w < 1) return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      dayCellHeightPx = entry.contentRect.height / w;
    });
    ro.observe(el);
    return () => ro.disconnect();
  });

  $effect(() => {
    const el = upcomingGridEl;
    if (!el || app.calendarView !== 'upcoming') return;
    const updateCols = (width: number) => {
      if (width < 760) upcomingCols = 2;
      else if (width < 1180) upcomingCols = 3;
      else upcomingCols = 4;
    };
    updateCols(el.clientWidth);
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      updateCols(entry.contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  });

  // Approximate line heights: balanced 0.7rem ~14px, dense 0.65rem leading-none ~11px
  const BALANCED_LINE_PX = 18;
  const BALANCED_RESERVED_PX = 32; // day number + padding
  const DENSE_LINE_PX = 14;
  const DENSE_RESERVED_PX = 14;

  const balancedMaxSlots = $derived(
    dayCellHeightPx > 0
      ? Math.max(1, Math.floor((dayCellHeightPx - BALANCED_RESERVED_PX) / BALANCED_LINE_PX))
      : 2
  );
  const denseMaxSlots = $derived(
    dayCellHeightPx > 0 ? Math.max(1, Math.floor((dayCellHeightPx - DENSE_RESERVED_PX) / DENSE_LINE_PX)) : 5
  );

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

  const MIN_EVENT_BLOCK_HEIGHT = 24;
  const MIN_TODO_BLOCK_HEIGHT = 40;
  const TIMED_EVENT_EXPANDED_HEIGHT_PX = 72;
  const TIMED_EVENT_SINGLE_LINE_HEIGHT_PX = 48;
  /** Day view: height of each hour row, scaled by user's height ratio (0.5–2). */
  const rowHeight = $derived(60 * app.calendarHeightRatio);

  const dayStartMs = $derived(
    new Date(selectedDate.getFullYear(), selectedDate.getMonth(), selectedDate.getDate()).getTime()
  );
  const dayEndMs = $derived(dayStartMs + 24 * 60 * 60 * 1000);

  const dayEventsAll = $derived(eventsForDay(selectedDate));
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
  function withOverlapLayout<T extends { startMin: number; endMin: number; type: 'event' | 'todo' }>(
    items: T[],
    hourRowHeightPx: number
  ): Array<T & { overlapColumn: number; overlapColumns: number; renderStartMin: number; renderEndMin: number }> {
    const groupMaxCols: number[] = [];
    const placed: Array<T & { overlapColumn: number; _group: number }> = [];
    let active: Array<{ end: number; col: number; group: number }> = [];
    let group = -1;

    for (const item of items) {
      active = active.filter((a) => a.end > item.startMin);

      if (active.length === 0) {
        group += 1;
        groupMaxCols[group] = 0;
      }

      const usedCols = new Set(active.map((a) => a.col));
      let col = 0;
      while (usedCols.has(col)) col += 1;

      const effectiveEnd = Math.max(item.endMin, item.startMin + 1 / 60);
      active.push({ end: effectiveEnd, col, group });

      groupMaxCols[group] = Math.max(groupMaxCols[group], col + 1, active.length);
      placed.push({ ...item, overlapColumn: col, _group: group });
    }

    const visualEndByCol = new Map<number, number>();
    const visualGapMin = (2 / hourRowHeightPx) * 60;

    const withVisualPosition = placed.map((p) => {
      const minHeightPx = p.type === 'todo' ? MIN_TODO_BLOCK_HEIGHT : MIN_EVENT_BLOCK_HEIGHT;
      const minDurationMin = (minHeightPx / hourRowHeightPx) * 60;
      const durationMin = Math.max(p.endMin - p.startMin, minDurationMin);
      const prevVisualEnd = visualEndByCol.get(p.overlapColumn) ?? -Infinity;
      const renderStartMin = Math.max(p.startMin, prevVisualEnd + visualGapMin);
      const renderEndMin = renderStartMin + durationMin;
      visualEndByCol.set(p.overlapColumn, renderEndMin);
      return { ...p, renderStartMin, renderEndMin };
    });

    return withVisualPosition.map((p) => ({
      ...p,
      overlapColumns: Math.max(1, groupMaxCols[p._group] ?? 1),
    }));
  }
  const timedItemsLaidOut = $derived(withOverlapLayout(timedItemsSorted, rowHeight));
  const dayItems = $derived([...allDayItems, ...timedItemsSorted]);

  function startOfLocalDay(d: Date): Date {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  const upcomingBaseDate = $derived(startOfLocalDay(new Date()));
  const upcomingDates = $derived(
    Array.from({ length: upcomingCols }, (_, i) =>
      new Date(upcomingBaseDate.getFullYear(), upcomingBaseDate.getMonth(), upcomingBaseDate.getDate() + i)
    )
  );

  function dayItemsForUpcoming(d: Date): Array<
    { kind: 'event'; startMs: number; event: Event }
    | { kind: 'todo'; startMs: number; todo: Todo }
  > {
    const dayStart = startOfLocalDay(d).getTime();
    const dayEvents = eventsForDay(d)
      .map((event) => ({
        kind: 'event' as const,
        startMs: event.all_day ? dayStart : parseUtcIfNeeded(event.start).getTime(),
        event,
      }));
    const dayTodos = showTodos
      ? todosForDay(d)
          .map((todo) => ({ kind: 'todo' as const, startMs: todo.due ? parseUtcIfNeeded(todo.due).getTime() : dayStart, todo }))
      : [];
    return [...dayEvents, ...dayTodos].sort((a, b) => a.startMs - b.startMs);
  }

  $effect(() => {
    if (app.calendarView !== 'upcoming') return;
    const maxDayIdx = Math.max(0, upcomingDates.length - 1);
    const clampedDayIdx = Math.max(0, Math.min(app.focusedDayIndex, maxDayIdx));
    if (clampedDayIdx !== app.focusedDayIndex) app.setFocusedDayIndex(clampedDayIdx);

    const focusedDate = upcomingDates[clampedDayIdx];
    if (!focusedDate) {
      if (app.focusedEventIndex !== -1) app.setFocusedEventIndex(-1);
      return;
    }

    app.setFocusedDayDate(focusedDate);
    const items = dayItemsForUpcoming(focusedDate);
    if (items.length === 0) {
      if (app.focusedEventIndex !== -1) app.setFocusedEventIndex(-1);
      return;
    }
    const clampedItemIdx = Math.max(0, Math.min(app.focusedEventIndex, items.length - 1));
    if (clampedItemIdx !== app.focusedEventIndex) app.setFocusedEventIndex(clampedItemIdx);
  });

  function findDayEventElement(req: { id: string; start: string; title: string }): HTMLElement | null {
    const dayItemsEls = Array.from(document.querySelectorAll('[data-day-item-index]')) as HTMLElement[];
    const byId = dayItemsEls.find((el) => el.getAttribute('data-day-item-event-id') === req.id);
    if (byId) return byId;

    const targetStartMs = parseUtcIfNeeded(req.start).getTime();
    const targetTitle = req.title.trim().toLowerCase();
    const candidates = dayItemsEls
      .map((el) => {
        const title = (el.getAttribute('data-day-item-event-title') || '').trim().toLowerCase();
        const startRaw = el.getAttribute('data-day-item-event-start') || '';
        const startMs = startRaw ? parseUtcIfNeeded(startRaw).getTime() : Number.NaN;
        return { el, title, startMs, startRaw };
      })
      .filter((x) => x.title && x.title === targetTitle && Number.isFinite(x.startMs));

    if (candidates.length === 0) return null;
    candidates.sort((a, b) => Math.abs(a.startMs - targetStartMs) - Math.abs(b.startMs - targetStartMs));
    return candidates[0].el;
  }

  // Created-event focus request from parent (used after creating from day view)
  $effect(() => {
    if (app.calendarView !== 'day') return;
    const req = focusEventRequest;
    if (!req) return;

    let cancelled = false;
    let attempts = 0;

    const tryFocus = () => {
      if (cancelled) return;
      attempts += 1;
      const el = findDayEventElement(req);
      if (el) {
        const indexAttr = el.getAttribute('data-day-item-index');
        const idx = indexAttr ? Number.parseInt(indexAttr, 10) : -1;
        if (idx >= 0) app.setFocusedEventIndex(idx);

        const bringIntoView = () => {
          el.focus({ preventScroll: true });
          el.scrollIntoView({ block: 'center', behavior: 'smooth' });
        };
        bringIntoView();
        setTimeout(bringIntoView, 120);

        onFocusEventRequestHandled?.();
        return;
      }

      if (attempts < 12) {
        setTimeout(tryFocus, 60);
      } else {
        onFocusEventRequestHandled?.();
      }
    };

    tick().then(tryFocus);
    return () => {
      cancelled = true;
    };
  });

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

  // Current time line: update continuously when viewing today
  let now = $state(new Date());
  $effect(() => {
    if (app.calendarView !== 'day' || !isToday(selectedDate)) return;
    let raf = 0;
    const updateNow = () => {
      now = new Date();
      raf = window.requestAnimationFrame(updateNow);
    };
    updateNow();
    return () => window.cancelAnimationFrame(raf);
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
      if (view === 'month') {
        const sel = calendarEl?.querySelector('.day-cell.selected') as HTMLElement | null;
        if (sel) sel.scrollIntoView({ block: 'nearest', behavior: 'smooth', inline: 'nearest' });
      } else if (view === 'day') {
        const nowLine = calendarEl?.querySelector('.day-view-now-line') as HTMLElement | null;
        const dayView = calendarEl?.querySelector('.day-view') as HTMLElement | null;
        if (nowLine && dayView) {
          const lineTop = nowLine.offsetTop;
          const target = Math.max(0, lineTop - dayView.clientHeight / 2);
          dayView.scrollTo({ top: target, behavior: 'smooth' });
        }
      }
    });
  });
</script>

<div id="calendar-view" class="p-4 flex-1 min-h-0 flex flex-col" style="--calendar-height-ratio: {app.calendarHeightRatio}; --calendar-row-height: calc(60px * var(--calendar-height-ratio, 1))" role="application" aria-label="Calendar" bind:this={calendarEl}>
  {#if app.calendarView === 'month'}
    <div class="flex flex-1 min-h-0 flex-col">
      <div class="calendar-month-header shrink-0">
        <h2 class="calendar-month-title text-xl font-semibold mb-3 text-[var(--text)]">
          {selectedDate.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
        </h2>
        <div class="calendar-weekday-header grid grid-cols-7 gap-1 mb-1 text-xs text-[var(--text-muted)]">
          {#each dayLabels as label}
            <span>{label}</span>
          {/each}
        </div>
      </div>
      <div class="calendar-month-grid-scroll flex-1 min-h-0 overflow-y-auto">
        <div
          bind:this={monthGridEl}
          class="grid grid-cols-7 gap-1 min-h-0"
          style="--calendar-weeks: {weeks}; height: calc(var(--calendar-row-height, 60px) * var(--calendar-weeks)); grid-template-rows: repeat({weeks}, 1fr);"
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
                    (document.querySelector(`[data-day-index="${next}"]`) as HTMLElement | null)?.focus();
                  }
                  if (e.key === 'ArrowUp' && i >= 7) {
                    app.setFocusedDayIndex(i - 7);
                    (document.querySelector(`[data-day-index="${i - 7}"]`) as HTMLElement | null)?.focus();
                  }
                }}
              >
              {#if density === 'minimal'}
                <span class="day-num-centered block text-2xl font-semibold">{d.getDate()}</span>
              {:else if density === 'dense'}
                {@const evs = eventsForDay(d)}
                {@const tds = showTodos ? todosForDay(d) : []}
                {@const combinedAll = [...evs.map((e) => ({ kind: 'event' as const, event: e })), ...tds.map((todo) => ({ kind: 'todo' as const, todo }))].sort((a, b) => {
                  const at = a.kind === 'event'
                    ? (a.event.all_day ? Number.NEGATIVE_INFINITY : parseUtcIfNeeded(a.event.start).getTime())
                    : (a.todo.due ? parseUtcIfNeeded(a.todo.due).getTime() : Number.POSITIVE_INFINITY);
                  const bt = b.kind === 'event'
                    ? (b.event.all_day ? Number.NEGATIVE_INFINITY : parseUtcIfNeeded(b.event.start).getTime())
                    : (b.todo.due ? parseUtcIfNeeded(b.todo.due).getTime() : Number.POSITIVE_INFINITY);
                  return at - bt;
                })}
                {@const denseHasMore = combinedAll.length > denseMaxSlots}
                {@const denseVisibleCount = denseHasMore ? Math.min(combinedAll.length, denseMaxSlots - 1) : Math.min(combinedAll.length, denseMaxSlots)}
                {@const combined = combinedAll.slice(0, denseVisibleCount)}
                <div class="dense-day-inner flex flex-row items-baseline gap-1.5 absolute inset-1 overflow-hidden text-left">
                  <span class="font-semibold text-sm shrink-0 leading-none">{d.getDate()}</span>
                  <div class="flex-1 min-w-0 overflow-hidden flex flex-col gap-0.5">
                    {#each combined as item}
                      {#if item.kind === 'event'}
                        <div class="dense-item text-[0.65rem] leading-tight" class:line-through={item.event.cancelled} title={item.event.title}>
                          <span class="dense-item-time">{item.event.all_day ? 'All day' : formatInTimezone(item.event.start, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)}</span>
                          <span class="dense-item-text dense-item-text-source" style={sourceColorStyle(item.event.source_id)}>{truncateDenseText(item.event.title)}</span>
                        </div>
                      {:else}
                        <div class="dense-item dense-item-todo text-[0.65rem] leading-tight italic text-[var(--text-muted)]" class:line-through={item.todo.completed} class:todo-overdue-text={isTodoOverdue(item.todo)} title={item.todo.summary} onclick={(e) => { e.preventDefault(); e.stopPropagation(); onSelectTodo?.(item.todo); }}>
                          <span class="dense-item-time">{item.todo.due ? formatInTimezone(item.todo.due, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined) : '–'}</span>
                          <span class="dense-item-text" class:dense-item-text-source={!item.todo.completed} style={!item.todo.completed ? sourceColorStyle(item.todo.source_id) : ''}>
                            {#if item.todo.completed}
                              ✓
                            {:else}
                              •
                            {/if}
                            {truncateDenseText(item.todo.summary)}
                          </span>
                        </div>
                      {/if}
                    {/each}
                    {#if denseHasMore}
                      <div class="text-[0.65rem] leading-none text-[var(--text-muted)] truncate">+{combinedAll.length - denseVisibleCount} more</div>
                    {/if}
                  </div>
                </div>
              {:else}
                <!-- balanced: events and todos combined, centered; (+N) only when truncated -->
                {@const evs = eventsForDay(d)}
                {@const tds = showTodos ? todosForDay(d) : []}
                {@const combinedAll = [...evs.map((e) => ({ kind: 'event' as const, event: e })), ...tds.map((t) => ({ kind: 'todo' as const, todo: t }))].sort((a, b) => {
                  const at = a.kind === 'event'
                    ? (a.event.all_day ? Number.NEGATIVE_INFINITY : parseUtcIfNeeded(a.event.start).getTime())
                    : (a.todo.due ? parseUtcIfNeeded(a.todo.due).getTime() : Number.POSITIVE_INFINITY);
                  const bt = b.kind === 'event'
                    ? (b.event.all_day ? Number.NEGATIVE_INFINITY : parseUtcIfNeeded(b.event.start).getTime())
                    : (b.todo.due ? parseUtcIfNeeded(b.todo.due).getTime() : Number.POSITIVE_INFINITY);
                  return at - bt;
                })}
                {@const balancedVisibleCount = combinedAll.length > balancedMaxSlots ? balancedMaxSlots - 1 : Math.min(combinedAll.length, balancedMaxSlots)}
                {@const visible = combinedAll.slice(0, balancedVisibleCount)}
                {@const hasMore = combinedAll.length > balancedVisibleCount}
                <span class="day-num-centered balanced-day-num block font-semibold">{d.getDate()}</span>
                <div class="balanced-view-content">
                  {#each visible as item}
                    {#if item.kind === 'event'}
                      <span class="balanced-item-marker balanced-item-marker-event" style={sourceColorStyle(item.event.source_id)} title={item.event.title}>
                        <span class="balanced-event-bar" aria-hidden="true"></span>
                      </span>
                    {:else}
                      <span class="balanced-item-marker balanced-item-marker-todo" class:is-completed={item.todo.completed} style={!item.todo.completed ? sourceColorStyle(item.todo.source_id) : ''} title={item.todo.summary} onclick={(e) => { e.preventDefault(); e.stopPropagation(); onSelectTodo?.(item.todo); }}>
                        <span class="balanced-todo-dot" aria-hidden="true"></span>
                        <span class="balanced-todo-bar" aria-hidden="true"></span>
                      </span>
                    {/if}
                  {/each}
                  {#if hasMore}
                    <span class="balanced-item-text block text-[0.82rem] overflow-hidden text-ellipsis whitespace-nowrap text-center text-[var(--text-muted)]">
                      +{combinedAll.length - balancedVisibleCount} more
                    </span>
                  {/if}
                </div>
              {/if}
              </button>
            {:else}
              <div class="day-cell bg-transparent border-none cursor-default"></div>
            {/if}
          {/each}
        </div>
      </div>
    </div>
  {:else if app.calendarView === 'upcoming'}
    <div class="upcoming-view flex flex-1 min-h-0 flex-col">
      <div class="upcoming-view-sticky-header shrink-0">
        <h3 class="upcoming-view-title mb-2">Upcoming</h3>
      </div>
      <div class="upcoming-grid flex-1 min-h-0" bind:this={upcomingGridEl} style={`--upcoming-cols: ${upcomingCols}`}>
        {#each upcomingDates as d, dayIdx}
          {@const items = dayItemsForUpcoming(d)}
          <section class="upcoming-day-col min-h-0" class:focused={app.focusedDayIndex === dayIdx} data-upcoming-day-index={dayIdx}>
            <h4 class="upcoming-day-heading">
              {d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
            </h4>
            <div class="upcoming-day-list">
              {#if items.length === 0}
                <p class="upcoming-empty">No events or todos.</p>
              {:else}
                {#each items as item, itemIdx}
                  {#if item.kind === 'event'}
                    {@const location = normalizeLocationText(item.event.location)}
                    <button
                      type="button"
                      class="day-event day-event-block upcoming-item"
                      style={sourceColorStyle(item.event.source_id)}
                      class:line-through={item.event.cancelled}
                      class:focused={app.focusedDayIndex === dayIdx && app.focusedEventIndex === itemIdx}
                      tabindex={app.focusedDayIndex === dayIdx && app.focusedEventIndex === itemIdx ? 0 : -1}
                      data-upcoming-item-index={itemIdx}
                      data-upcoming-item-kind="event"
                      onfocus={() => {
                        app.setFocusedDayIndex(dayIdx);
                        app.setFocusedDayDate(d);
                        app.setFocusedEventIndex(itemIdx);
                      }}
                      onclick={() => onSelectEvent?.(item.event)}
                    >
                      <span class="upcoming-item-time">
                        {#if item.event.all_day}
                          All day
                        {:else}
                          {formatInTimezone(item.event.start, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)}
                          {#if item.event.end}
                            – {formatInTimezone(item.event.end, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)}
                          {/if}
                        {/if}
                      </span>
                      <span class="upcoming-item-title">{location ? `${item.event.title} @ ${location}` : item.event.title}</span>
                    </button>
                  {:else}
                    <button
                      type="button"
                      class="day-todo day-todo-block upcoming-item"
                      style={sourceColorStyle(item.todo.source_id)}
                      class:focused={app.focusedDayIndex === dayIdx && app.focusedEventIndex === itemIdx}
                      class:completed={item.todo.completed}
                      class:overdue={isTodoOverdue(item.todo)}
                      disabled={loadingTodoId === item.todo.id}
                      tabindex={app.focusedDayIndex === dayIdx && app.focusedEventIndex === itemIdx ? 0 : -1}
                      data-upcoming-item-index={itemIdx}
                      data-upcoming-item-kind="todo"
                      data-upcoming-item-todo-id={item.todo.id}
                      onfocus={() => {
                        app.setFocusedDayIndex(dayIdx);
                        app.setFocusedDayDate(d);
                        app.setFocusedEventIndex(itemIdx);
                      }}
                      onclick={() => onSelectTodo?.(item.todo)}
                    >
                      {#if loadingTodoId === item.todo.id}
                        <span class="flex items-center gap-2 text-[var(--text-muted)]" aria-busy="true" aria-live="polite">
                          <span class="todo-loading-spinner" aria-hidden="true"></span>
                          Updating…
                        </span>
                      {:else}
                        <span class="day-todo-checkbox" aria-hidden="true">
                          {#if item.todo.completed}✓{:else}<span class="checkbox-empty"></span>{/if}
                        </span>
                        <span class="upcoming-item-main">
                          <span class="upcoming-item-time">
                            {item.todo.due ? formatInTimezone(item.todo.due, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined) : 'No due time'}
                          </span>
                          <span class="upcoming-item-title">{item.todo.summary}</span>
                        </span>
                      {/if}
                    </button>
                  {/if}
                {/each}
              {/if}
            </div>
          </section>
        {/each}
      </div>
    </div>
  {:else}
    <!-- Day view: 24h timeline -->
    <div class="day-view flex flex-col flex-1 min-h-0">
      <div class="day-view-sticky-header shrink-0">
        <h3 class="day-view-title mb-2">{selectedDate.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</h3>
        {#if dayItems.length === 0}
          <p class="text-[var(--text-muted)] mb-2">No events or todos this day.</p>
        {/if}
      </div>

      {#if allDayItems.length > 0}
        <div class="day-view-allday shrink-0 mb-2">
          <span class="day-view-allday-label">All day</span>
          <div class="day-view-allday-items">
            {#each allDayItems as item, i}
              {#if item.type === 'event'}
                {@const location = normalizeLocationText(item.event.location)}
                <button
                  type="button"
                  class="day-event day-event-block"
                  style={sourceColorStyle(item.event.source_id)}
                  class:focused={app.focusedEventIndex === i}
                  class:line-through={item.event.cancelled}
                  tabindex={app.focusedEventIndex === i ? 0 : -1}
                  data-day-item-index={i}
                  data-day-item-event-id={item.event.id}
                  data-day-item-event-title={item.event.title}
                  data-day-item-event-start={item.event.start}
                  onfocus={() => app.setFocusedEventIndex(i)}
                  onclick={() => onSelectEvent?.(item.event)}
                >
                  <span class="day-event-title">{item.event.title}</span>
                  {#if location}
                    <span class="day-event-location">{location}</span>
                  {/if}
                </button>
              {:else}
                <button
                  type="button"
                  class="day-todo day-todo-block"
                  style={sourceColorStyle(item.todo.source_id)}
                  class:focused={app.focusedEventIndex === i}
                  class:completed={item.todo.completed}
                  class:overdue={isTodoOverdue(item.todo)}
                  disabled={loadingTodoId === item.todo.id}
                  tabindex={app.focusedEventIndex === i ? 0 : -1}
                  data-day-item-index={i}
                  data-day-item-todo-id={item.todo.id}
                  onfocus={() => app.setFocusedEventIndex(i)}
                  onclick={() => onSelectTodo?.(item.todo)}
                >
                  {#if loadingTodoId === item.todo.id}
                    <span class="flex items-center gap-2 text-[var(--text-muted)]" aria-busy="true" aria-live="polite">
                      <span class="todo-loading-spinner" aria-hidden="true"></span>
                      Updating…
                    </span>
                  {:else}
                    <span class="day-todo-checkbox" aria-hidden="true">
                      {#if item.todo.completed}✓{:else}<span class="checkbox-empty"></span>{/if}
                    </span>
                    <span class="day-todo-label">{item.todo.summary}</span>
                  {/if}
                </button>
              {/if}
            {/each}
          </div>
        </div>
      {/if}

      <div class="day-view-timeline-wrap flex-1 min-h-0 flex flex-col">
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

          <div class="day-view-items-layer">
            {#each timedItemsLaidOut as item, idx}
            {@const i = allDayItems.length + idx}
            {@const topPx = item.renderStartMin / 60 * rowHeight}
            {@const heightPx = Math.max(1, (item.renderEndMin - item.renderStartMin) / 60 * rowHeight)}
            {@const isCompactTimedEvent = item.type === 'event' && heightPx < TIMED_EVENT_SINGLE_LINE_HEIGHT_PX}
            {@const isInlineLocationTimedEvent = item.type === 'event' && !isCompactTimedEvent && heightPx < TIMED_EVENT_EXPANDED_HEIGHT_PX}
            {@const leftPct = item.overlapColumn / item.overlapColumns * 100}
            {@const widthPct = 100 / item.overlapColumns}
            {@const laneGapPx = 4}
            {#if item.type === 'event'}
              {@const location = normalizeLocationText(item.event.location)}
              <button
                type="button"
                class="day-event day-event-timed"
                style={`${sourceColorStyle(item.event.source_id)} top: ${topPx}px; height: ${heightPx}px; left: calc(${leftPct}% + ${laneGapPx / 2}px); width: calc(${widthPct}% - ${laneGapPx}px);`}
                class:day-event-compact={isCompactTimedEvent}
                class:focused={app.focusedEventIndex === i}
                class:line-through={item.event.cancelled}
                tabindex={app.focusedEventIndex === i ? 0 : -1}
                data-day-item-index={i}
                data-day-item-event-id={item.event.id}
                data-day-item-event-title={item.event.title}
                data-day-item-event-start={item.event.start}
                onfocus={() => app.setFocusedEventIndex(i)}
                onclick={() => onSelectEvent?.(item.event)}
              >
                <span class="day-event-time">
                  {formatInTimezone(item.event.start, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)}
                  {#if item.event.end && !isCompactTimedEvent}
                    – {formatInTimezone(item.event.end, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)}
                  {/if}
                </span>
                <span class="day-event-title">
                  {(isCompactTimedEvent || isInlineLocationTimedEvent) && location
                    ? `${item.event.title} @ ${location}`
                    : item.event.title}
                </span>
                {#if !isCompactTimedEvent && !isInlineLocationTimedEvent && location}
                  <span class="day-event-location">{location}</span>
                {/if}
              </button>
            {:else}
                <button
                  type="button"
                  class="day-todo day-todo-timed"
                  style={`${sourceColorStyle(item.todo.source_id)} top: ${topPx}px; height: ${heightPx}px; left: calc(${leftPct}% + ${laneGapPx / 2}px); width: calc(${widthPct}% - ${laneGapPx}px);`}
                  class:focused={app.focusedEventIndex === i}
                  class:completed={item.todo.completed}
                  class:overdue={isTodoOverdue(item.todo)}
                  disabled={loadingTodoId === item.todo.id}
                  tabindex={app.focusedEventIndex === i ? 0 : -1}
                  data-day-item-index={i}
                  data-day-item-todo-id={item.todo.id}
                  onfocus={() => app.setFocusedEventIndex(i)}
                  onclick={() => onSelectTodo?.(item.todo)}
                >
                  {#if loadingTodoId === item.todo.id}
                    <span class="flex items-center gap-2 text-[var(--text-muted)]" aria-busy="true" aria-live="polite">
                      <span class="todo-loading-spinner" aria-hidden="true"></span>
                      Updating…
                    </span>
                  {:else}
                    <span class="day-todo-checkbox" aria-hidden="true">
                      {#if item.todo.completed}✓{:else}<span class="checkbox-empty"></span>{/if}
                    </span>
                    <span class="day-todo-main">
                      <span class="day-todo-time">
                        {formatInTimezone(item.todo.due ?? '', { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)}
                      </span>
                      <span class="day-todo-label">{item.todo.summary}</span>
                    </span>
                  {/if}
                </button>
              {/if}
            {/each}
          </div>
        </div>
      </div>

    </div>
  {/if}
</div>
