<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
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

<div class="toolbar">
  <span>Calslop</span>
  <label>
    Theme
    <select class="theme-select" bind:value={themeValue} onchange={handleThemeChange}>
      <option value="system">System</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
    </select>
  </label>
  <a href="/settings" class="btn btn-ghost">Settings</a>
  <button class="btn btn-ghost" onclick={() => app.setModalOpen('shortcuts')} type="button">
    ? Shortcuts
  </button>
</div>

<KeyboardHandler />

<main id="main">
  {@render children()}
</main>
