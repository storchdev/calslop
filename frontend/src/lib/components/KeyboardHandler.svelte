<script lang="ts">
  import { onMount } from 'svelte';
  import { app } from '$lib/stores/app.svelte';
  import { addDays, addMonths } from '$lib/date';

  function isInputFocused() {
    if (typeof document === 'undefined') return false;
    const el = document.activeElement;
    if (!el) return false;
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role');
    const editable = el.getAttribute('contenteditable') === 'true';
    return (
      tag === 'input' ||
      tag === 'textarea' ||
      tag === 'select' ||
      role === 'textbox' ||
      role === 'combobox' ||
      editable
    );
  }

  function handleKeydown(e: KeyboardEvent) {
    if (isInputFocused()) return;

    const key = e.key.toLowerCase();
    const ctrl = e.ctrlKey;
    const alt = e.altKey;
    const meta = e.metaKey;
    if (ctrl || alt || meta) return; // avoid browser shortcuts

    // Escape closes any open modal (so it works even when modal div doesn't have focus)
    if (app.modalOpen && key === 'escape') {
      const was = app.modalOpen;
      app.setModalOpen(null);
      if (was === 'event' || was === 'todo') app.setEditingId(null);
      e.preventDefault();
      return;
    }
    if (app.modalOpen) return; // no other global shortcuts when modal open

    // Day view: j/k move focus between events/todos, Enter opens focused item (work even when focus is not on the list)
    if (app.viewMode === 'calendar' && app.calendarView === 'day') {
      const dayItems = Array.from(document.querySelectorAll('[data-day-item-index]'));
      if (dayItems.length > 0) {
        if (key === 'j' || key === 'arrowdown') {
          e.preventDefault();
          const curr = app.focusedEventIndex;
          const next = curr < 0 ? 0 : Math.min(curr + 1, dayItems.length - 1);
          app.setFocusedEventIndex(next);
          (dayItems[next] as HTMLElement)?.focus();
          return;
        }
        if (key === 'k' || key === 'arrowup') {
          e.preventDefault();
          const curr = app.focusedEventIndex;
          const next = curr < 0 ? dayItems.length - 1 : Math.max(0, curr - 1);
          app.setFocusedEventIndex(next);
          (dayItems[next] as HTMLElement)?.focus();
          return;
        }
        if (key === 'enter') {
          const curr = app.focusedEventIndex;
          if (curr >= 0 && curr < dayItems.length) {
            e.preventDefault();
            (dayItems[curr] as HTMLElement)?.click();
            return;
          }
        }
      }
    }

    // Todo view: S toggles show completed; j/k move focus, Enter opens, Space/x toggle completed
    if (app.viewMode === 'todo') {
      if (key === 's') {
        app.toggleShowCompletedTodos();
        e.preventDefault();
        return;
      }
      const todoItems = Array.from(document.querySelectorAll('[data-todo-item-index]'));
      if (todoItems.length > 0) {
        if (key === 'j' || key === 'arrowdown') {
          e.preventDefault();
          const curr = app.focusedTodoIndex;
          const next = curr < 0 ? 0 : Math.min(curr + 1, todoItems.length - 1);
          app.setFocusedTodoIndex(next);
          (todoItems[next] as HTMLElement)?.focus();
          return;
        }
        if (key === 'k' || key === 'arrowup') {
          e.preventDefault();
          const curr = app.focusedTodoIndex;
          const next = curr < 0 ? todoItems.length - 1 : Math.max(0, curr - 1);
          app.setFocusedTodoIndex(next);
          (todoItems[next] as HTMLElement)?.focus();
          return;
        }
        if (key === 'enter') {
          const curr = app.focusedTodoIndex;
          if (curr >= 0 && curr < todoItems.length) {
            e.preventDefault();
            (todoItems[curr] as HTMLElement)?.click();
            return;
          }
        }
        if (key === ' ' || key === 'x') {
          e.preventDefault();
          const curr = app.focusedTodoIndex;
          if (curr >= 0 && curr < todoItems.length) {
            const row = todoItems[curr];
            const checkbox = row?.querySelector('input[type="checkbox"]') as HTMLInputElement | null;
            if (checkbox) {
              checkbox.checked = !checkbox.checked;
              checkbox.dispatchEvent(new Event('change', { bubbles: true }));
            }
            return;
          }
        }
      }
    }

    if (app.viewMode === 'calendar' && app.calendarView === 'month' && key === 'enter') {
      const dateToUse = app.focusedDayDate ?? app.selectedDate;
      app.setSelectedDate(dateToUse);
      app.setCalendarView('day');
      e.preventDefault();
      return;
    }

    // h/j/k/l and arrows: navigate in calendar view (use calendar math to avoid DST bugs)
    if (app.viewMode === 'calendar' && !e.repeat) {
      const d = app.selectedDate;
      const shift = e.shiftKey;
      const isMonthView = app.calendarView === 'month';
      const isDayView = app.calendarView === 'day';
      let next: Date | null = null;

      if (shift) {
        if (isMonthView) {
          if (key === 'h' || key === 'arrowleft') next = addMonths(d, -1);
          if (key === 'l' || key === 'arrowright') next = addMonths(d, 1);
          if (key === 'j' || key === 'arrowdown') next = addMonths(d, 1);
          if (key === 'k' || key === 'arrowup') next = addMonths(d, -1);
        } else {
          if (key === 'h' || key === 'arrowleft') next = addDays(d, -7);
          if (key === 'l' || key === 'arrowright') next = addDays(d, 7);
          // j/k in day view are for events/todos, not week
          if (key === 'j' || key === 'arrowdown') next = addDays(d, 7);
          if (key === 'k' || key === 'arrowup') next = addDays(d, -7);
        }
      } else {
        if (key === 'h' || key === 'arrowleft') next = addDays(d, -1);
        if (key === 'l' || key === 'arrowright') next = addDays(d, 1);
        // In day view, j/k are used for moving between events/todos; only h/l change the day
        if (!isDayView) {
          if (key === 'j' || key === 'arrowdown') next = addDays(d, 7);
          if (key === 'k' || key === 'arrowup') next = addDays(d, -7);
        }
      }
      if (next) {
        app.setSelectedDate(next);
        e.preventDefault();
        return;
      }
    }

    switch (key) {
      case '1':
      case 'c':
        if (!e.repeat) app.setViewMode('calendar');
        e.preventDefault();
        break;
      case '2':
      case 't':
        if (!e.repeat) app.setViewMode('todo');
        e.preventDefault();
        break;
      case 'd':
        if (!e.repeat && app.viewMode === 'calendar') app.setCalendarView('day');
        e.preventDefault();
        break;
      case 'm':
        if (!e.repeat && app.viewMode === 'calendar') app.setCalendarView('month');
        e.preventDefault();
        break;
      case 'v':
        if (!e.repeat && app.viewMode === 'calendar') app.cycleCalendarDensity();
        e.preventDefault();
        break;
      case 'y':
        if (!e.repeat && app.viewMode === 'calendar') app.toggleShowTodosOnCalendar();
        e.preventDefault();
        break;
      case 'g':
        if (e.key === 'g' && !e.shiftKey) {
          // gg = go to today (second g within 500ms)
          app.goToToday();
          e.preventDefault();
        }
        break;
      case 'home':
        app.goToToday();
        e.preventDefault();
        break;
      case 'n':
        if (!e.repeat) {
          if (app.viewMode === 'calendar') app.setModalOpen('event');
          else app.setModalOpen('todo');
        }
        e.preventDefault();
        break;
      case '?':
        app.setModalOpen('shortcuts');
        e.preventDefault();
        break;
      default:
        break;
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown, true);
    return () => window.removeEventListener('keydown', handleKeydown, true);
  });
</script>
