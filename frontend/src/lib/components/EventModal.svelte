<script lang="ts">
  import { createEvent, updateEvent, getEvent, deleteEvent } from '$lib/api';
  import type { Event, EventCreate, EventUpdate } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';

  interface Props {
    onclose: () => void;
    onsave: () => void;
  }

  let { onclose, onsave }: Props = $props();

  let title = $state('');
  let start = $state('');
  let end = $state('');
  let allDay = $state(false);
  let description = $state('');
  let sourceId = $state('');
  let sources = $state<{ id: string; name: string; type: string }[]>([]);
  let error = $state('');
  let saving = $state(false);

  const editingId = $derived(app.editingId);

  $effect(() => {
    if (editingId) {
      getEvent(editingId).then((e) => {
        title = e.title;
        start = e.start.slice(0, 16);
        end = e.end.slice(0, 16);
        allDay = e.all_day;
        description = e.description ?? '';
      });
    } else {
      const d = app.selectedDate;
      title = '';
      start = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T09:00`;
      end = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T10:00`;
      allDay = false;
      description = '';
    }
  });

  import { getSources } from '$lib/api';
  $effect(() => {
    getSources().then((s) => {
      sources = s.filter((x) => x.type === 'local_folder' || x.type === 'caldav').map((x) => ({ id: x.id, name: x.name, type: x.type }));
      if (sources.length && !editingId) sourceId = sources[0].id;
    });
  });

  async function submit() {
    error = '';
    if (!title.trim()) {
      error = 'Title is required';
      return;
    }
    saving = true;
    try {
      if (editingId) {
        await updateEvent(editingId, { title: title.trim(), start, end, all_day: allDay, description: description || null });
      } else {
        if (!sourceId) {
          error = 'Select a calendar source';
          return;
        }
        await createEvent({ source_id: sourceId, title: title.trim(), start, end, all_day: allDay, description: description || null });
      }
      onsave();
      onclose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to save';
    } finally {
      saving = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }
</script>

<div class="modal-backdrop" role="dialog" aria-modal="true" onkeydown={handleKeydown} onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="modal" onclick={(e) => e.stopPropagation()}>
    <h2>{editingId ? 'Edit event' : 'New event'}</h2>
    {#if error}
      <p class="error">{error}</p>
    {/if}
    {#if !editingId}
      <div class="form-row">
        <label>Calendar</label>
        <select bind:value={sourceId}>
          {#each sources as s}
            <option value={s.id}>{s.name}</option>
          {/each}
        </select>
      </div>
    {/if}
    <div class="form-row">
      <label>Title</label>
      <input type="text" bind:value={title} />
    </div>
    <div class="form-row">
      <label>Start</label>
      <input type="datetime-local" bind:value={start} disabled={allDay} />
    </div>
    <div class="form-row">
      <label>End</label>
      <input type="datetime-local" bind:value={end} disabled={allDay} />
    </div>
    <div class="form-row">
      <label><input type="checkbox" bind:checked={allDay} /> All day</label>
    </div>
    <div class="form-row">
      <label>Description</label>
      <textarea bind:value={description} rows="3"></textarea>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick={submit} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
      {#if editingId}
        <button
          class="btn btn-ghost"
          type="button"
          disabled={saving}
          onclick={async () => {
            if (!confirm('Delete this event?')) return;
            try {
              await deleteEvent(editingId);
              onsave();
              onclose();
            } catch (e) {
              error = e instanceof Error ? e.message : 'Failed to delete';
            }
          }}
        >Delete</button>
      {/if}
      <button class="btn btn-ghost" onclick={onclose} type="button">Cancel</button>
    </div>
  </div>
</div>

<style>
  .error {
    color: #dc2626;
    font-size: 0.875rem;
  }
</style>
