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
    // Escape clears search when not in modal and search is active
    if (!app.modalOpen && key === 'escape' && app.searchQuery) {
      app.clearSearch();
      e.preventDefault();
      return;
    }
    if (app.modalOpen) return; // no other global shortcuts when modal open

    // Slash focuses search bar (month view or todo view)
    if (key === '/') {
      const el = document.getElementById('calslop-search-input') as HTMLInputElement | null;
      if (
        el &&
        (app.viewMode === 'todo' || (app.viewMode === 'calendar' && app.calendarView === 'month'))
      ) {
        el.focus();
        e.preventDefault();
      }
      return;
    }

    // Day view: J/K jump between events/todos, j/k scroll timeline, Enter open edit, x toggle todo
    if (app.viewMode === 'calendar' && app.calendarView === 'day') {
      const dayItems = Array.from(document.querySelectorAll('[data-day-item-index]'));
      const scrollEl =
        (document.querySelector('#calendar-view .day-view') as HTMLElement | null)
        ?? (document.querySelector('.content-scroll') as HTMLElement | null);
      const scrollAmount = 80;

      if (e.key === 'J' || (e.key === 'j' && e.shiftKey)) {
        e.preventDefault();
        if (dayItems.length > 0) {
          const curr = app.focusedEventIndex;
          const next = curr < 0 ? 0 : Math.min(curr + 1, dayItems.length - 1);
          app.setFocusedEventIndex(next);
          const el = dayItems[next] as HTMLElement;
          el?.focus();
          el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
        return;
      }
      if (e.key === 'K' || (e.key === 'k' && e.shiftKey)) {
        e.preventDefault();
        if (dayItems.length > 0) {
          const curr = app.focusedEventIndex;
          const next = curr < 0 ? dayItems.length - 1 : Math.max(0, curr - 1);
          app.setFocusedEventIndex(next);
          const el = dayItems[next] as HTMLElement;
          el?.focus();
          el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
        return;
      }
      if (e.key === 'j' && !e.shiftKey) {
        e.preventDefault();
        if (scrollEl) scrollEl.scrollTop = Math.min(scrollEl.scrollHeight - scrollEl.clientHeight, scrollEl.scrollTop + scrollAmount);
        return;
      }
      if (e.key === 'k' && !e.shiftKey) {
        e.preventDefault();
        if (scrollEl) scrollEl.scrollTop = Math.max(0, scrollEl.scrollTop - scrollAmount);
        return;
      }
      if (e.key === 'x') {
        const active = document.activeElement as HTMLElement | null;
        const todoId = active?.getAttribute?.('data-day-item-todo-id');
        if (todoId) {
          e.preventDefault();
          window.dispatchEvent(new CustomEvent('calslop-toggle-day-todo', { detail: { todoId } }));
        }
        return;
      }
      if (key === 'enter' && dayItems.length > 0) {
        const curr = app.focusedEventIndex;
        if (curr >= 0 && curr < dayItems.length) {
          e.preventDefault();
          (dayItems[curr] as HTMLElement)?.click();
        }
        return;
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

    function focusFirstDayItemSoon() {
      setTimeout(() => {
        const firstDayItem = document.querySelector('[data-day-item-index="0"]') as HTMLElement | null;
        if (!firstDayItem) return;
        app.setFocusedEventIndex(0);
        firstDayItem.focus();
        firstDayItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }, 0);
    }

    if (app.viewMode === 'calendar' && app.calendarView === 'month' && key === 'enter') {
      const dateToUse = app.focusedDayDate ?? app.selectedDate;
      app.setSelectedDate(dateToUse);
      app.setCalendarView('day');
      focusFirstDayItemSoon();
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
        if (
          isDayView
          && !shift
          && (key === 'h' || key === 'l' || key === 'arrowleft' || key === 'arrowright')
        ) {
          focusFirstDayItemSoon();
        }
        e.preventDefault();
        return;
      }
    }

    // Search mode (calendar month): N = next highlighted day, Shift+N = previous
    if (
      key === 'n' &&
      !e.repeat &&
      app.viewMode === 'calendar' &&
      app.calendarView === 'month' &&
      app.searchQuery &&
      app.highlightedDayIndices.length > 0
    ) {
      const indices = app.highlightedDayIndices;
      const curr = app.focusedDayIndex;
      const dateForIndex = (i: number) => {
        const startPad = new Date(app.selectedDate.getFullYear(), app.selectedDate.getMonth(), 1).getDay();
        const day = i - startPad + 1;
        const daysInMonth = new Date(app.selectedDate.getFullYear(), app.selectedDate.getMonth() + 1, 0).getDate();
        if (day < 1 || day > daysInMonth) return null;
        return new Date(app.selectedDate.getFullYear(), app.selectedDate.getMonth(), day);
      };
      if (e.shiftKey) {
        const prevIndices = indices.filter((i) => i < curr);
        const nextIdx = prevIndices.length > 0 ? prevIndices[prevIndices.length - 1] : indices[indices.length - 1];
        const d = dateForIndex(nextIdx);
        if (d) {
          app.setFocusedDayIndex(nextIdx);
          app.setFocusedDayDate(d);
          app.setSelectedDate(d);
          (document.querySelector(`[data-day-index="${nextIdx}"]`) as HTMLElement | null)?.focus();
        }
      } else {
        const nextIndices = indices.filter((i) => i > curr);
        const nextIdx = nextIndices.length > 0 ? nextIndices[0] : indices[0];
        const d = dateForIndex(nextIdx);
        if (d) {
          app.setFocusedDayIndex(nextIdx);
          app.setFocusedDayDate(d);
          app.setSelectedDate(d);
          (document.querySelector(`[data-day-index="${nextIdx}"]`) as HTMLElement | null)?.focus();
        }
      }
      e.preventDefault();
      return;
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
      case 'r':
        if (!e.repeat) {
          window.dispatchEvent(new CustomEvent('calslop-sync'));
        }
        e.preventDefault();
        break;
      case 'b':
        if (!e.repeat) app.setNavbarCollapsed(!app.navbarCollapsed);
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
