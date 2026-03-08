<script lang="ts">
  import { onMount } from 'svelte';
  import { getSources, createSource, deleteSource } from '$lib/api';
  import { app } from '$lib/stores/app.svelte';
  import type { Source } from '$lib/types';

  let sources = $state<Source[]>([]);
  let loading = $state(true);
  let error = $state('');
  let adding = $state(false);
  let newType = $state<'ics_url' | 'local_folder' | 'caldav'>('ics_url');
  let newName = $state('');
  let newConfig = $state<Record<string, string>>({});

  function load() {
    loading = true;
    getSources()
      .then((s) => {
        sources = s;
      })
      .catch((e) => (error = e.message))
      .finally(() => (loading = false));
  }

  onMount(() => {
    load();
  });

  async function addSource() {
    error = '';
    if (!newName.trim()) {
      error = 'Name is required';
      return;
    }
    if (newType === 'ics_url' && !newConfig['url']) {
      error = 'URL is required for ICS subscription';
      return;
    }
    if (newType === 'local_folder' && !newConfig['path']) {
      error = 'Path is required for local folder';
      return;
    }
    if (newType === 'caldav' && !newConfig['url']) {
      error = 'CalDAV URL is required';
      return;
    }
    try {
      await createSource({
        type: newType,
        name: newName.trim(),
        config: { ...newConfig },
      });
      adding = false;
      newName = '';
      newConfig = {};
      load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to add source';
    }
  }

  async function remove(id: string) {
    if (!confirm('Remove this source?')) return;
    try {
      await deleteSource(id);
      load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to remove';
    }
  }

  function configFields(): { key: string; label: string; placeholder: string }[] {
    if (newType === 'ics_url') return [{ key: 'url', label: 'ICS URL', placeholder: 'https://...' }];
    if (newType === 'local_folder') return [{ key: 'path', label: 'Folder path', placeholder: '/path/to/folder' }];
    return [
      { key: 'url', label: 'CalDAV URL', placeholder: 'https://...' },
      { key: 'username', label: 'Username', placeholder: '' },
      { key: 'password', label: 'Password', placeholder: '' },
    ];
  }

  function sourceTypeLabel(type: Source['type']): string {
    if (type === 'ics_url') return 'Read-only ICS URL';
    if (type === 'local_folder') return 'Local .ics folder';
    return 'CalDAV server';
  }
</script>

<svelte:head>
  <title>Settings – Calslop</title>
</svelte:head>

<div class="settings-page">
  <h1>Settings</h1>
  <a href="/" class="back-link">← Back to calendar</a>

  <h2>Calendar &amp; todo sources</h2>
  {#if error}
    <p class="text-red-600" style="margin: 0 0 0.75rem;">{error}</p>
  {/if}
  {#if loading}
    <p style="margin: 0;">Loading…</p>
  {:else}
    <ul class="settings-sources-list">
      <li class="settings-sources-header">
        <span class="source-name">Name</span>
        <span class="source-type">Type</span>
        <span class="source-remove"></span>
      </li>
      {#each sources as s}
        <li>
          <span class="source-name">{s.name}</span>
          <span class="source-type">{sourceTypeLabel(s.type)}</span>
          <button class="btn btn-ghost source-remove" onclick={() => remove(s.id)} type="button">Remove</button>
        </li>
      {/each}
    </ul>
    {#if adding}
      <form class="add-form" onsubmit={(e) => { e.preventDefault(); addSource(); }}>
        <div class="form-row">
          <label for="new-name">Name</label>
          <input id="new-name" type="text" bind:value={newName} placeholder="My calendar" />
        </div>
        <div class="form-row">
          <label for="new-type">Type</label>
          <select id="new-type" bind:value={newType}>
            <option value="ics_url">Read-only ICS URL</option>
            <option value="local_folder">Local .ics folder</option>
            <option value="caldav">CalDAV server</option>
          </select>
        </div>
        {#each configFields() as f}
          <div class="form-row">
            <label for="config-{f.key}">{f.label}</label>
            <input
              id="config-{f.key}"
              type={f.key === 'password' ? 'password' : 'text'}
              bind:value={newConfig[f.key]}
              placeholder={f.placeholder}
            />
          </div>
        {/each}
        <div class="form-actions">
          <button class="btn btn-primary" type="submit">Add</button>
          <button class="btn btn-ghost" type="button" onclick={() => (adding = false)}>Cancel</button>
        </div>
      </form>
    {:else}
      <button class="btn btn-primary add-source-btn" onclick={() => (adding = true)} type="button">Add source</button>
    {/if}
  {/if}

  <h2>Sync</h2>
  <div class="form-row" style="max-width: 18rem;">
    <label for="auto-sync-interval">Auto-sync</label>
    <select
      id="auto-sync-interval"
      value={app.autoSyncInterval}
      onchange={(e) => app.setAutoSyncInterval((e.currentTarget as HTMLSelectElement).value as 'off' | '30s' | '1m' | '5m')}
    >
      <option value="off">Off</option>
      <option value="30s">Every 30 seconds</option>
      <option value="1m">Every 1 minute</option>
      <option value="5m">Every 5 minutes</option>
    </select>
  </div>
</div>
