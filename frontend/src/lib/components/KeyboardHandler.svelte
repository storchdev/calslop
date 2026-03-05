<script lang="ts">
  import { onMount } from 'svelte';
  import { app } from '$lib/stores/app.svelte';

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

    // h/j/k/l and arrows: navigate in calendar view
    if (app.viewMode === 'calendar' && !e.repeat) {
      const d = app.selectedDate;
      const shift = e.shiftKey;
      const isMonthView = app.calendarView === 'month';
      let next: Date | null = null;

      if (shift) {
        // Shift: month in month view, week in day view
        if (isMonthView) {
          if (key === 'h' || key === 'arrowleft') next = new Date(d.getFullYear(), d.getMonth() - 1, d.getDate());
          if (key === 'l' || key === 'arrowright') next = new Date(d.getFullYear(), d.getMonth() + 1, d.getDate());
          if (key === 'j' || key === 'arrowdown') next = new Date(d.getFullYear(), d.getMonth() + 1, d.getDate());
          if (key === 'k' || key === 'arrowup') next = new Date(d.getFullYear(), d.getMonth() - 1, d.getDate());
        } else {
          if (key === 'h' || key === 'arrowleft') next = new Date(d.getTime() - 7 * 24 * 60 * 60 * 1000);
          if (key === 'l' || key === 'arrowright') next = new Date(d.getTime() + 7 * 24 * 60 * 60 * 1000);
          if (key === 'j' || key === 'arrowdown') next = new Date(d.getTime() + 7 * 24 * 60 * 60 * 1000);
          if (key === 'k' || key === 'arrowup') next = new Date(d.getTime() - 7 * 24 * 60 * 60 * 1000);
        }
      } else {
        // No shift: h/l = day, j/k = week
        if (key === 'h' || key === 'arrowleft') next = new Date(d.getFullYear(), d.getMonth(), d.getDate() - 1);
        if (key === 'l' || key === 'arrowright') next = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1);
        if (key === 'j' || key === 'arrowdown') next = new Date(d.getTime() + 7 * 24 * 60 * 60 * 1000);
        if (key === 'k' || key === 'arrowup') next = new Date(d.getTime() - 7 * 24 * 60 * 60 * 1000);
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
