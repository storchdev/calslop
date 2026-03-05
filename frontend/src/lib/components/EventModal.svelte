<script lang="ts">
  import { tick } from 'svelte';
  import { createEvent, updateEvent, getEvent, deleteEvent } from '$lib/api';
  import type { Event, EventCreate, EventUpdate } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { toLocalDatetimeInput } from '$lib/date';

  interface Props {
    initialEvent?: Event | null;
    onclose: () => void;
    onsave: () => void;
  }

  let { initialEvent = null, onclose, onsave }: Props = $props();

  let title = $state('');
  let start = $state('');
  let end = $state('');
  let allDay = $state(false);
  let description = $state('');
  let location = $state('');
  let recurrence = $state('');
  let sourceId = $state('');
  let sources = $state<{ id: string; name: string; type: string }[]>([]);
  let error = $state('');
  let saving = $state(false);

  const editingId = $derived(app.editingId);

  const repeatOptions = [
    { value: '', label: 'None' },
    { value: 'FREQ=DAILY', label: 'Daily' },
    { value: 'FREQ=WEEKLY', label: 'Weekly' },
    { value: 'FREQ=MONTHLY', label: 'Monthly' },
    { value: 'FREQ=YEARLY', label: 'Yearly' },
  ];

  $effect(() => {
    const tz = app.timezone || undefined;
    if (editingId) {
      const prefill = initialEvent?.id === editingId ? initialEvent : null;
      if (prefill) {
        title = prefill.title;
        start = toLocalDatetimeInput(prefill.start, tz);
        end = toLocalDatetimeInput(prefill.end, tz);
        allDay = prefill.all_day;
        description = prefill.description ?? '';
        location = prefill.location ?? '';
        recurrence = prefill.recurrence ?? '';
      } else {
        getEvent(editingId).then((e) => {
          title = e.title;
          start = toLocalDatetimeInput(e.start, tz);
          end = toLocalDatetimeInput(e.end, tz);
          allDay = e.all_day;
          description = e.description ?? '';
          location = e.location ?? '';
          recurrence = e.recurrence ?? '';
        });
      }
    } else {
      const d = app.selectedDate;
      title = '';
      start = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T09:00`;
      end = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T10:00`;
      allDay = false;
      description = '';
      location = '';
      recurrence = '';
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
    const startIso = new Date(start).toISOString();
    const endIso = new Date(end).toISOString();
    saving = true;
    try {
      if (editingId) {
        await updateEvent(editingId, {
          title: title.trim(),
          start: startIso,
          end: endIso,
          all_day: allDay,
          description: description || null,
          location: location.trim() || null,
          recurrence: recurrence || null,
        });
      } else {
        if (!sourceId) {
          error = 'Select a calendar source';
          return;
        }
        await createEvent({
          source_id: sourceId,
          title: title.trim(),
          start: startIso,
          end: endIso,
          all_day: allDay,
          description: description || null,
          location: location.trim() || null,
          recurrence: recurrence || null,
        });
      }
      onsave();
      onclose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to save';
    } finally {
      saving = false;
    }
  }

  let modalEl: HTMLDivElement | undefined;
  let titleEl: HTMLInputElement | undefined;
  let startEl: HTMLInputElement | undefined;
  let endEl: HTMLInputElement | undefined;
  let allDayEl: HTMLInputElement | undefined;
  let locationEl: HTMLInputElement | undefined;
  let recurrenceEl: HTMLSelectElement | undefined;
  let descriptionEl: HTMLTextAreaElement | undefined;
  let sourceIdEl: HTMLSelectElement | undefined;

  $effect(() => {
    if (app.modalOpen === 'event') {
      tick().then(() => modalEl?.focus());
    }
  });

  function cycleSelect(sel: HTMLSelectElement, dir: 1 | -1) {
    const opts = Array.from(sel.options);
    const i = opts.findIndex((o) => o.value === sel.value);
    const next = Math.max(0, Math.min(opts.length - 1, i + dir));
    sel.selectedIndex = next;
    sel.value = opts[next].value;
    sel.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function handleKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement;
    const inTextInput = target instanceof HTMLInputElement && target.type !== 'checkbox' && target.type !== 'radio'
      || target instanceof HTMLTextAreaElement;

    if (e.key === 'Escape') {
      if (inTextInput) {
        e.preventDefault();
        target.blur();
        modalEl?.focus();
      } else {
        onclose();
      }
      return;
    }
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      submit();
      return;
    }
    if (editingId && e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'd') {
      e.preventDefault();
      if (confirm('Delete this event?')) {
        deleteEvent(editingId).then(() => {
          onsave();
          onclose();
        }).catch((err) => {
          error = err instanceof Error ? err.message : 'Failed to delete';
        });
      }
      return;
    }
    if (target instanceof HTMLSelectElement) {
      if (e.shiftKey && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        cycleSelect(target, 1);
        return;
      }
      if (e.shiftKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        cycleSelect(target, -1);
        return;
      }
    }
    if (inTextInput) return;

    const key = e.key.toLowerCase();
    if (key === 't') {
      e.preventDefault();
      titleEl?.focus();
    } else if (key === 's') {
      e.preventDefault();
      startEl?.focus();
    } else if (key === 'e') {
      e.preventDefault();
      endEl?.focus();
    } else if (key === 'a') {
      e.preventDefault();
      allDayEl?.focus();
    } else if (key === 'l') {
      e.preventDefault();
      locationEl?.focus();
    } else if (key === 'r') {
      e.preventDefault();
      recurrenceEl?.focus();
    } else if (key === 'd') {
      e.preventDefault();
      descriptionEl?.focus();
    } else if (key === 'c' && sourceIdEl) {
      e.preventDefault();
      sourceIdEl.focus();
    }
  }
</script>

<div class="modal-backdrop" role="dialog" aria-modal="true" onkeydown={handleKeydown} onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="modal" tabindex="-1" bind:this={modalEl} onclick={(e) => e.stopPropagation()}>
    <h2>{editingId ? 'Edit event' : 'New event'}</h2>
    {#if error}
      <p class="text-red-600 text-sm">{error}</p>
    {/if}
    {#if !editingId}
      <div class="form-row">
        <div class="form-row-header">
          <span class="field-label">Calendar</span>
          <span class="field-shortcut">C</span>
        </div>
        <select bind:value={sourceId} bind:this={sourceIdEl}>
          {#each sources as s}
            <option value={s.id}>{s.name}</option>
          {/each}
        </select>
      </div>
    {/if}
    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Title</span>
        <span class="field-shortcut">T</span>
      </div>
      <input type="text" bind:value={title} bind:this={titleEl} />
    </div>
    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Start</span>
        <span class="field-shortcut">S</span>
      </div>
      <input type="datetime-local" bind:value={start} disabled={allDay} bind:this={startEl} />
    </div>
    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">End</span>
        <span class="field-shortcut">E</span>
      </div>
      <input type="datetime-local" bind:value={end} disabled={allDay} bind:this={endEl} />
    </div>
    <div class="form-row form-row-checkbox">
      <div class="form-row-header">
        <span class="field-label">All day</span>
        <span class="field-shortcut">A</span>
      </div>
      <label class="checkbox-label">
        <input type="checkbox" bind:checked={allDay} bind:this={allDayEl} />
      </label>
    </div>
    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Location</span>
        <span class="field-shortcut">L</span>
      </div>
      <input type="text" bind:value={location} placeholder="e.g. Conference room A" bind:this={locationEl} />
    </div>
    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Repeat</span>
        <span class="field-shortcut">R</span>
      </div>
      <select bind:value={recurrence} bind:this={recurrenceEl}>
        {#each repeatOptions as opt}
          <option value={opt.value}>{opt.label}</option>
        {/each}
      </select>
    </div>
    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Description</span>
        <span class="field-shortcut">D</span>
      </div>
      <textarea bind:value={description} rows="3" bind:this={descriptionEl}></textarea>
    </div>
    <div class="form-actions">
      <div class="form-action-with-hint">
        <button class="btn btn-primary" onclick={submit} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
        <span class="action-hint">Ctrl+Enter</span>
      </div>
      {#if editingId}
        <div class="form-action-with-hint">
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
          <span class="action-hint">Ctrl+Shift+D</span>
        </div>
      {/if}
      <div class="form-action-with-hint">
        <button class="btn btn-ghost" onclick={onclose} type="button">Cancel</button>
        <span class="action-hint">Esc</span>
      </div>
    </div>
  </div>
</div>
