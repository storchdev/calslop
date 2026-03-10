<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    getSources,
    createSource,
    deleteSource,
    getNotificationSettings,
    sendTestNotification,
    updateNotificationSettings,
    updateSource,
  } from '$lib/api';
  import { app } from '$lib/stores/app.svelte';
  import type { NotificationTarget, Source } from '$lib/types';
  import { sourceColorForIndex } from '$lib/source-colors';

  let sources = $state<Source[]>([]);
  let loading = $state(true);
  let error = $state('');
  let adding = $state(false);
  let newType = $state<'ics_url' | 'local_folder' | 'caldav'>('ics_url');
  let newName = $state('');
  let newConfig = $state<Record<string, string>>({});
  let notificationsEnabled = $state(false);
  let notificationTarget = $state<NotificationTarget>('notify_send');
  let webhookUrl = $state('');
  let webhookHeadersText = $state('{}');
  let emailTo = $state('');
  let notificationTimeFormat = $state('%b %d %H:%M %Z');
  let notificationBodyTemplate = $state('{time}');
  let notificationsLoading = $state(true);
  let notificationsSaving = $state(false);
  let testingNotification = $state(false);
  let notificationsMessage = $state('');

  function load() {
    loading = true;
    getSources()
      .then((s) => {
        sources = s;
      })
      .catch((e) => (error = e.message))
      .finally(() => (loading = false));
  }

  function loadNotificationSettings() {
    notificationsLoading = true;
    getNotificationSettings()
      .then((settings) => {
        notificationsEnabled = settings.enabled;
        notificationTarget = settings.target;
        webhookUrl = settings.webhook.url ?? '';
        webhookHeadersText = JSON.stringify(settings.webhook.headers ?? {}, null, 2);
        emailTo = settings.email.to ?? '';
        notificationTimeFormat = settings.time_format || '%b %d %H:%M %Z';
        notificationBodyTemplate = settings.body_template || '{time}';
        notificationsMessage = settings.health_error ?? '';
      })
      .catch((e) => {
        notificationsMessage = e instanceof Error ? e.message : 'Failed to load notification settings';
      })
      .finally(() => {
        notificationsLoading = false;
      });
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      goto('/');
    }
  }

  onMount(() => {
    load();
    loadNotificationSettings();

    window.addEventListener('keydown', handleKeydown);
    return () => {
      window.removeEventListener('keydown', handleKeydown);
    };
  });

  function parseHeadersOrThrow(): Record<string, string> {
    const text = webhookHeadersText.trim();
    if (!text) return {};
    const value = JSON.parse(text);
    if (!value || Array.isArray(value) || typeof value !== 'object') {
      throw new Error('Webhook headers must be a JSON object');
    }
    const headers: Record<string, string> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      headers[k] = String(v);
    }
    return headers;
  }

  async function saveNotificationSettings() {
    notificationsSaving = true;
    notificationsMessage = '';
    try {
      const headers = parseHeadersOrThrow();
      const settings = await updateNotificationSettings({
        enabled: notificationsEnabled,
        target: notificationTarget,
        webhook: { url: webhookUrl || null, headers },
        email: { to: emailTo || null },
        time_format: notificationTimeFormat,
        body_template: notificationBodyTemplate,
      });
      notificationsEnabled = settings.enabled;
      notificationTarget = settings.target;
      notificationsMessage = settings.health_error ?? 'Notification settings saved.';
      app.setDesktopNotificationsEnabled(settings.enabled);
    } catch (e) {
      notificationsMessage = e instanceof Error ? e.message : 'Failed to save notification settings';
    } finally {
      notificationsSaving = false;
    }
  }

  async function testNotification() {
    testingNotification = true;
    notificationsMessage = '';
    try {
      await sendTestNotification();
      notificationsMessage = 'Test notification sent.';
    } catch (e) {
      notificationsMessage = e instanceof Error ? e.message : 'Failed to send test notification';
    } finally {
      testingNotification = false;
    }
  }

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

  function sourceColor(s: Source, index: number): string {
    return sourceColorForIndex(s, index);
  }

  async function changeSourceColor(sourceId: string, color: string) {
    error = '';
    try {
      await updateSource(sourceId, { color });
      sources = sources.map((s) => (s.id === sourceId ? { ...s, color } : s));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to update source color';
      load();
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
        <span class="source-color">Color</span>
        <span class="source-remove"></span>
      </li>
      {#each sources as s, i}
        <li>
          <span class="source-name">{s.name}</span>
          <span class="source-type">{sourceTypeLabel(s.type)}</span>
          <label class="source-color">
            <input
              class="source-color-input"
              type="color"
              value={sourceColor(s, i)}
              aria-label={`Color for ${s.name}`}
              onchange={(e) => changeSourceColor(s.id, (e.currentTarget as HTMLInputElement).value)}
            />
          </label>
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
  <div class="form-row" style="max-width: 18rem;">
    <label for="time-display-format">Time display</label>
    <select
      id="time-display-format"
      value={app.timeDisplayFormat}
      onchange={(e) => app.setTimeDisplayFormat((e.currentTarget as HTMLSelectElement).value as '24h' | '12h')}
    >
      <option value="24h">24-hour (13:30)</option>
      <option value="12h">12-hour (1:30 PM)</option>
    </select>
  </div>

  <h2>Notifications</h2>
  {#if notificationsLoading}
    <p style="margin: 0;">Loading…</p>
  {:else}
    <div class="form-row" style="max-width: 18rem;">
      <label for="notifications-enabled">Enabled</label>
      <input id="notifications-enabled" type="checkbox" bind:checked={notificationsEnabled} />
    </div>
    <div class="form-row" style="max-width: 18rem;">
      <label for="notification-target">Target</label>
      <select id="notification-target" bind:value={notificationTarget}>
        <option value="notify_send">notify-send</option>
        <option value="webhook">webhook</option>
        <option value="email">email</option>
      </select>
    </div>
    {#if notificationTarget === 'webhook'}
      <div class="form-row" style="max-width: 40rem;">
        <label for="notification-webhook-url">Webhook URL</label>
        <input id="notification-webhook-url" type="text" bind:value={webhookUrl} placeholder="https://..." />
      </div>
      <div class="form-row" style="max-width: 40rem;">
        <label for="notification-webhook-headers">Headers (JSON)</label>
        <textarea id="notification-webhook-headers" bind:value={webhookHeadersText} rows="6"></textarea>
      </div>
    {:else if notificationTarget === 'email'}
      <div class="form-row" style="max-width: 30rem;">
        <label for="notification-email-to">Recipient email</label>
        <input id="notification-email-to" type="email" bind:value={emailTo} placeholder="you@example.com" />
      </div>
    {/if}
    <div class="form-row" style="max-width: 30rem;">
      <label for="notification-time-format">Time format</label>
      <input
        id="notification-time-format"
        type="text"
        bind:value={notificationTimeFormat}
        placeholder="%b %d %H:%M %Z"
      />
    </div>
    <div class="form-row" style="max-width: 40rem;">
      <label for="notification-body-template">Body template</label>
      <textarea
        id="notification-body-template"
        bind:value={notificationBodyTemplate}
        rows="4"
        placeholder={'{time}\n{delta}'}
      ></textarea>
      <small>Available fields: {'{time}'}, {'{delta}'}, {'{title}'}, {'{kind}'}. Use new lines as needed.</small>
    </div>
    <div class="form-actions" style="margin-top: 0.5rem;">
      <button class="btn btn-primary" type="button" onclick={saveNotificationSettings} disabled={notificationsSaving}>
        {notificationsSaving ? 'Saving…' : 'Save notifications'}
      </button>
      <button class="btn btn-ghost" type="button" onclick={testNotification} disabled={testingNotification}>
        {testingNotification ? 'Sending…' : 'Send test notification'}
      </button>
    </div>
    {#if notificationsMessage}
      <p style="margin-top: 0.5rem;">{notificationsMessage}</p>
    {/if}
  {/if}
</div>
