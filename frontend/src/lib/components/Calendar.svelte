<script lang="ts">
  import type { Event, Todo } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { formatInTimezone } from '$lib/date';

  interface Props {
    events: Event[];
    todos?: Todo[];
    selectedDate: Date;
    onSelectDay?: (d: Date) => void;
    onSelectEvent?: (ev: Event) => void;
    onSelectTodo?: (todo: Todo) => void;
  }

  let { events, todos = [], selectedDate, onSelectDay, onSelectEvent, onSelectTodo }: Props = $props();

  const density = $derived(app.calendarDensity);
  const showTodos = $derived(app.showTodosOnCalendar);

  const monthStart = $derived(new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1));
  const monthEnd = $derived(new Date(selectedDate.getFullYear(), selectedDate.getMonth() + 1, 0));
  const startPad = $derived((monthStart.getDay() + 6) % 7); // Monday first
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
      const due = new Date(t.due);
      return due.getDate() === d.getDate() && due.getMonth() === d.getMonth() && due.getFullYear() === d.getFullYear();
    });
  }

  const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  // When switching to month view, sync focused day to selected date so Enter works without re-focusing a cell
  $effect(() => {
    if (app.calendarView !== 'month') return;
    const d = selectedDate;
    const idx = startPad + d.getDate() - 1;
    app.setFocusedDayDate(d);
    app.setFocusedDayIndex(idx);
  });

  // Day view: keep focused item index in range; set to 0 when there are items and index was invalid
  $effect(() => {
    if (app.calendarView !== 'day') return;
    const dayEvents = events.filter((e) => {
      const d = new Date(e.start);
      return d.getDate() === selectedDate.getDate() && d.getMonth() === selectedDate.getMonth() && d.getFullYear() === selectedDate.getFullYear();
    });
    const dayTodos = showTodos ? todosForDay(selectedDate) : [];
    const dayItems = [...dayEvents.map((e) => ({ type: 'event' as const, event: e, sort: new Date(e.start).getTime() })), ...dayTodos.map((t) => ({ type: 'todo' as const, todo: t, sort: new Date(t.due ?? 0).getTime() }))].sort((a, b) => a.sort - b.sort);
    if (dayItems.length === 0) {
      app.setFocusedEventIndex(-1);
      return;
    }
    if (app.focusedEventIndex < 0 || app.focusedEventIndex >= dayItems.length) {
      app.setFocusedEventIndex(0);
    }
  });
</script>

<div id="calendar-view" class="p-4 flex-1 min-h-0 flex flex-col" role="application" aria-label="Calendar">
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
                        <div class="text-[0.65rem] overflow-hidden text-ellipsis whitespace-nowrap flex items-center gap-0.5 leading-none" title={item.todo.summary} onclick={(e) => { e.preventDefault(); e.stopPropagation(); onSelectTodo?.(item.todo); }}>
                          {#if item.todo.completed}
                            <span class="opacity-70 shrink-0" aria-hidden="true">✓</span>
                          {:else}
                            <span class="opacity-70 border border-current rounded w-3 h-3 inline-block shrink-0" aria-hidden="true"></span>
                          {/if}
                          {item.todo.due ? formatInTimezone(item.todo.due, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined) : '–'} {item.todo.summary}
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
                      <span class="block text-[0.7rem] overflow-hidden text-ellipsis whitespace-nowrap flex items-center justify-center gap-0.5" title={item.todo.summary} onclick={(e) => { e.preventDefault(); e.stopPropagation(); onSelectTodo?.(item.todo); }}>
                        {#if item.todo.completed}
                          <span class="opacity-70" aria-hidden="true">✓</span>
                        {:else}
                          <span class="opacity-70 border border-current rounded w-3 h-3 inline-block shrink-0" aria-hidden="true"></span>
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
    {#if true}
      {@const dayEvents = events.filter((e) => {
        const d = new Date(e.start);
        return d.getDate() === selectedDate.getDate() && d.getMonth() === selectedDate.getMonth() && d.getFullYear() === selectedDate.getFullYear();
      })}
      {@const dayTodos = showTodos ? todosForDay(selectedDate) : []}
      {@const dayItems = [...dayEvents.map((e) => ({ type: 'event' as const, event: e, sort: new Date(e.start).getTime() })), ...dayTodos.map((t) => ({ type: 'todo' as const, todo: t, sort: new Date(t.due ?? 0).getTime() }))].sort((a, b) => a.sort - b.sort)}
      <div>
        <h3 class="mb-3">{selectedDate.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</h3>
        <ul class="list-none p-0 m-0">
          {#each dayItems as item, i}
            {#if item.type === 'event'}
              <li class="mb-1">
                <button
                  type="button"
                  class="event-item"
                  class:focused={app.focusedEventIndex === i}
                  class:line-through={item.event.cancelled}
                  tabindex={app.focusedEventIndex === i ? 0 : -1}
                  data-day-item-index={i}
                  onfocus={() => app.setFocusedEventIndex(i)}
                  onclick={() => onSelectEvent?.(item.event)}
                  onkeydown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      onSelectEvent?.(item.event);
                      return;
                    }
                    if (e.key === 'j' || e.key === 'ArrowDown') {
                      e.preventDefault();
                      if (i < dayItems.length - 1) {
                        app.setFocusedEventIndex(i + 1);
                        (e.currentTarget as HTMLElement).parentElement?.nextElementSibling?.querySelector('[data-day-item-index]')?.focus();
                      }
                    }
                    if (e.key === 'k' || e.key === 'ArrowUp') {
                      e.preventDefault();
                      if (i > 0) {
                        app.setFocusedEventIndex(i - 1);
                        (e.currentTarget as HTMLElement).parentElement?.previousElementSibling?.querySelector('[data-day-item-index]')?.focus();
                      }
                    }
                  }}
                >
                  {item.event.all_day ? 'All day' : formatInTimezone(item.event.start, { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)} – {item.event.title}
                </button>
              </li>
            {:else}
              <li class="mb-1">
                <button
                  type="button"
                  class="event-item italic text-[var(--text-muted)]"
                  class:focused={app.focusedEventIndex === i}
                  tabindex={app.focusedEventIndex === i ? 0 : -1}
                  data-day-item-index={i}
                  onfocus={() => app.setFocusedEventIndex(i)}
                  onclick={() => onSelectTodo?.(item.todo)}
                  onkeydown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      onSelectTodo?.(item.todo);
                      return;
                    }
                    if (e.key === 'j' || e.key === 'ArrowDown') {
                      e.preventDefault();
                      if (i < dayItems.length - 1) {
                        app.setFocusedEventIndex(i + 1);
                        (e.currentTarget as HTMLElement).parentElement?.nextElementSibling?.querySelector('[data-day-item-index]')?.focus();
                      }
                    }
                    if (e.key === 'k' || e.key === 'ArrowUp') {
                      e.preventDefault();
                      if (i > 0) {
                        app.setFocusedEventIndex(i - 1);
                        (e.currentTarget as HTMLElement).parentElement?.previousElementSibling?.querySelector('[data-day-item-index]')?.focus();
                      }
                    }
                  }}
                >
                  {#if item.todo.completed}
                    <span class="mr-1.5 opacity-70" aria-hidden="true">✓</span>
                  {:else}
                    <span class="mr-1.5 opacity-70 border border-current rounded w-3.5 h-3.5 inline-block shrink-0 align-middle" aria-hidden="true"></span>
                  {/if}
                  {formatInTimezone(item.todo.due ?? '', { hour: '2-digit', minute: '2-digit' }, app.timezone || undefined)} – {item.todo.summary}
                </button>
              </li>
            {/if}
          {/each}
        </ul>
        {#if dayItems.length === 0}
          <p class="text-[var(--text-muted)]">No events or todos this day.</p>
        {/if}
      </div>
    {/if}
  {/if}
</div>
