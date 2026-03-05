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
    const tz = localStorage.getItem('calslop-timezone');
    if (tz !== null) app.setTimezone(tz);
  });

  function handleTimezoneChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    const v = target.value;
    app.setTimezone(v);
    localStorage.setItem('calslop-timezone', v);
  }

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

<div class="toolbar">
  <div class="dropdown-box">
    <span class="dropdown-box-label">Theme</span>
    <select bind:value={themeValue} onchange={handleThemeChange}>
      <option value="system">System</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
    </select>
  </div>
  <div class="dropdown-box">
    <span class="dropdown-box-label">Time zone</span>
    <select value={app.timezone} onchange={handleTimezoneChange}>
      <option value="">Local (browser)</option>
      <option value="America/New_York">Eastern</option>
      <option value="America/Chicago">Central</option>
      <option value="America/Denver">Mountain</option>
      <option value="America/Los_Angeles">Pacific</option>
      <option value="Europe/London">London</option>
      <option value="Europe/Paris">Paris</option>
      <option value="Asia/Tokyo">Tokyo</option>
      <option value="UTC">UTC</option>
    </select>
  </div>
  <a href="/settings" class="btn btn-ghost">Settings</a>
  <button class="btn btn-ghost inline-flex items-baseline gap-1.5" onclick={() => app.setModalOpen('shortcuts')} type="button">
    Shortcuts
    <span class="key-hint">?</span>
  </button>
</div>

<KeyboardHandler />

{#if $navigating}
  <div class="nav-loading" role="status" aria-live="polite">Loading…</div>
{/if}

<main id="main">
  {@render children()}
</main>
