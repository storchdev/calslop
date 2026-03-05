<script lang="ts">
  import { getSources, createSource, deleteSource } from '$lib/api';
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

  $effect(() => load());

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
</script>

<svelte:head>
  <title>Settings – Calslop</title>
</svelte:head>

<div class="settings">
  <h1>Settings</h1>
  <p><a href="/">← Back to calendar</a></p>

  <h2>Calendar &amp; todo sources</h2>
  {#if error}
    <p class="error">{error}</p>
  {/if}
  {#if loading}
    <p>Loading…</p>
  {:else}
    <ul class="sources-list">
      {#each sources as s}
        <li>
          <span class="source-name">{s.name}</span>
          <span class="source-type">{s.type}</span>
          <button class="btn btn-ghost" onclick={() => remove(s.id)} type="button">Remove</button>
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
      <button class="btn btn-primary" onclick={() => (adding = true)} type="button">Add source</button>
    {/if}
  {/if}
</div>

<style>
  .settings {
    padding: 1rem;
    max-width: 600px;
  }
  .sources-list {
    list-style: none;
    padding: 0;
  }
  .sources-list li {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border);
  }
  .source-name {
    font-weight: 600;
  }
  .source-type {
    color: var(--text-muted);
    font-size: 0.875rem;
  }
  .add-form {
    margin-top: 1rem;
  }
  .error {
    color: #dc2626;
  }
</style>
