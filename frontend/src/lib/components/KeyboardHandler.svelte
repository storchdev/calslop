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
    if (app.modalOpen) return; // no global shortcuts when modal open

    const key = e.key.toLowerCase();
    const ctrl = e.ctrlKey;
    const alt = e.altKey;
    const meta = e.metaKey;
    if (ctrl || alt || meta) return; // avoid browser shortcuts

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
