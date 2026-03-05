<script lang="ts">
  import type { Event } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';

  interface Props {
    events: Event[];
    selectedDate: Date;
    onSelectDay?: (d: Date) => void;
    onSelectEvent?: (ev: Event) => void;
  }

  let { events, selectedDate, onSelectDay, onSelectEvent }: Props = $props();

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

  const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
</script>

<div id="calendar-view" class="calendar" role="application" aria-label="Calendar">
  {#if app.calendarView === 'month'}
    <div class="calendar-month">
      <div class="calendar-weekdays">
        {#each dayLabels as label}
          <span class="calendar-weekday">{label}</span>
        {/each}
      </div>
      <div class="calendar-grid" role="grid">
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
              onclick={() => {
                app.setSelectedDate(d);
                onSelectDay?.(d);
              }}
              onkeydown={(e) => {
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
              <span class="day-num">{d.getDate()}</span>
              {#each eventsForDay(d).slice(0, 2) as ev}
                <span class="day-event" title={ev.title}>{ev.title}</span>
              {/each}
              {#if eventsForDay(d).length > 2}
                <span class="day-more">+{eventsForDay(d).length - 2}</span>
              {/if}
            </button>
          {:else}
            <div class="day-cell empty"></div>
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
      <div class="calendar-day">
        <h3>{selectedDate.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</h3>
        <ul class="day-events-list">
          {#each dayEvents as ev, i}
          <li>
            <button
              type="button"
              class="event-item"
              class:focused={app.focusedEventIndex === i}
              tabindex={app.focusedEventIndex === i ? 0 : -1}
              onclick={() => onSelectEvent?.(ev)}
            >
              {ev.all_day ? 'All day' : new Date(ev.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} – {ev.title}
            </button>
          </li>
          {/each}
        </ul>
        {#if dayEvents.length === 0}
          <p class="text-muted">No events this day.</p>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .calendar {
    padding: 1rem;
  }
  .calendar-weekdays {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
    margin-bottom: 4px;
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .calendar-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
  }
  .day-cell.empty {
    min-height: 60px;
    background: transparent;
    border: none;
    cursor: default;
  }
  .day-num {
    display: block;
    font-weight: 600;
  }
  .day-event, .day-more {
    display: block;
    font-size: 0.7rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .calendar-day h3 {
    margin-bottom: 0.75rem;
  }
  .day-events-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  .day-events-list li {
    margin-bottom: 0.25rem;
  }
  .text-muted {
    color: var(--text-muted);
  }
</style>
