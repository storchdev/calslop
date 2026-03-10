<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { navigating } from '$app/stores';
  import { app } from '$lib/stores/app.svelte';
  import { setTheme } from '$lib/theme';
  import KeyboardHandler from '$lib/components/KeyboardHandler.svelte';

  let { children } = $props();
  let themeValue = $state<'light' | 'dark' | 'system'>('system');

  onMount(() => {
    const stored = localStorage.getItem('calslop-theme') as 'light' | 'dark' | 'system' | null;
    if (stored) {
      themeValue = stored;
      setTheme(stored);
    }
    const ratio = localStorage.getItem('calslop-calendar-height-ratio');
    if (ratio !== null) {
      const r = parseFloat(ratio);
      if (!Number.isNaN(r)) app.setCalendarHeightRatio(r);
    }
    const navCollapsed = localStorage.getItem('calslop-navbar-collapsed');
    if (navCollapsed === '1') app.setNavbarCollapsed(true);
    const autoSyncInterval = localStorage.getItem('calslop-auto-sync-interval');
    if (autoSyncInterval === 'off' || autoSyncInterval === '30s' || autoSyncInterval === '1m' || autoSyncInterval === '5m') {
      app.setAutoSyncInterval(autoSyncInterval);
    }
    const timeDisplayFormat = localStorage.getItem('calslop-time-display-format');
    if (timeDisplayFormat === '24h' || timeDisplayFormat === '12h') {
      app.setTimeDisplayFormat(timeDisplayFormat);
    }
  });

  function handleThemeChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    const v = target.value as 'light' | 'dark' | 'system';
    themeValue = v;
    setTheme(v);
    localStorage.setItem('calslop-theme', v);
  }
</script>

<svelte:head>
  <title>Calslop</title>
</svelte:head>

<a href="#main" class="skip-link">Skip to main content</a>
<a href="#calendar-view" class="skip-link">Skip to calendar</a>
<a href="#todo-view" class="skip-link">Skip to todos</a>

{#if !app.navbarCollapsed}
  <div class="navbar-wrap">
    <div class="toolbar">
      <div class="toolbar-left">
        <button
          class="btn btn-ghost inline-flex items-baseline gap-1.5"
          class:bg-[var(--bg-elevated)]={app.viewMode === 'calendar'}
          class:font-semibold={app.viewMode === 'calendar'}
          onclick={() => app.setViewMode('calendar')}
          type="button"
        >
          Calendar
          <span class="key-hint">1</span>
        </button>
        <button
          class="btn btn-ghost inline-flex items-baseline gap-1.5"
          class:bg-[var(--bg-elevated)]={app.viewMode === 'todo'}
          class:font-semibold={app.viewMode === 'todo'}
          onclick={() => app.setViewMode('todo')}
          type="button"
        >
          Todos
          <span class="key-hint">2</span>
        </button>
        {#if app.viewMode === 'calendar'}
          <button
            class="btn btn-ghost inline-flex items-baseline gap-1.5"
            class:bg-[var(--bg-elevated)]={app.calendarView === 'month'}
            class:font-semibold={app.calendarView === 'month'}
            onclick={() => app.setCalendarView('month')}
            type="button"
          >
            Month
            <span class="key-hint">M</span>
          </button>
          <button
            class="btn btn-ghost inline-flex items-baseline gap-1.5"
            class:bg-[var(--bg-elevated)]={app.calendarView === 'day'}
            class:font-semibold={app.calendarView === 'day'}
            onclick={() => app.setCalendarView('day')}
            type="button"
          >
            Day
            <span class="key-hint">D</span>
          </button>
          <button
            class="btn btn-ghost inline-flex items-baseline gap-1.5"
            class:bg-[var(--bg-elevated)]={app.calendarView === 'upcoming'}
            class:font-semibold={app.calendarView === 'upcoming'}
            onclick={() => app.setCalendarView('upcoming')}
            type="button"
          >
            Upcoming
            <span class="key-hint">U</span>
          </button>
        {/if}
      </div>
      <div class="toolbar-right">
        <div class="dropdown-box">
          <span class="dropdown-box-label">Theme</span>
          <select bind:value={themeValue} onchange={handleThemeChange}>
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>
        <a href="/settings" class="btn btn-ghost">Settings</a>
        <button class="btn btn-ghost inline-flex items-baseline gap-1.5" onclick={() => app.setModalOpen('shortcuts')} type="button">
          Shortcuts
          <span class="key-hint">?</span>
        </button>
        <button class="btn btn-ghost inline-flex items-baseline gap-1.5" type="button" onclick={() => app.setNavbarCollapsed(true)} title="Hide navbar (B)">
          ▲ Hide nav
          <span class="key-hint">B</span>
        </button>
      </div>
    </div>
  </div>
{/if}

<KeyboardHandler />

{#if $navigating}
  <div class="nav-loading" role="status" aria-live="polite">Loading…</div>
{/if}

{#if app.apiLoading && !$navigating}
  <div class="api-loading-indicator" role="status" aria-live="polite">
    <span class="todo-loading-spinner" aria-hidden="true"></span>
    Loading…
  </div>
{/if}

<main id="main">
  {@render children()}
</main>
