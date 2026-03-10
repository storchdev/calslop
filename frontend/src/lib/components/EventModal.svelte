<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { createEvent, updateEvent, getEvent, deleteEvent, getSources, parseHumanDatetime, parseHumanRecurrence, parseHumanAlerts, parseHumanDelta } from '$lib/api';
  import type { Event, SourceType } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { toLocalDatetimeInput } from '$lib/date';
  import {
    alertOptions,
    buildAlertSelectState,
    cycleSelectOption,
    getPreferredTimezone,
    repeatOptions,
    resolveAlertMinutesFromSelection,
    resolveAlertMinutesForSubmit,
  } from '$lib/modal-utils';
  import { handleCommonModalKeydown, isTextInputTarget } from '$lib/modal-keyboard';
  import { activateAndFocus, blurInputAndFocusModal, clearIfFocusOutside } from '$lib/modal-focus';

interface Props {
  initialEvent?: Event | null;
  onclose: () => void;
  onsave: (saved?: { id: string; start: string; title: string }) => void | Promise<void>;
}

  let { initialEvent = null, onclose, onsave }: Props = $props();

  let title = $state('');
  let start = $state('');
  let end = $state('');
  let allDay = $state(false);
  let description = $state('');
  let location = $state('');
  let recurrence = $state('');
  let alertMinutesBefore = $state<number[]>([]);
  let alertSelectValue = $state('');
  let sourceId = $state('');
  let sources = $state<{ id: string; name: string; type: string }[]>([]);
  let sourceTypes = $state<Record<string, SourceType>>({});
  let error = $state('');
  let saving = $state(false);
  let deleting = $state(false);
  let activeDateField = $state<'start' | 'end' | null>(null);
  let activeRepeatField = $state(false);
  let activeAlertField = $state(false);
  let startHuman = $state('');
  let endHuman = $state('');
  let repeatHuman = $state('');
  let alertHuman = $state('');
  let shiftHuman = $state('');
  let shiftDeltaSeconds = $state(0);
  let shiftDeltaLabel = $state('');
  let shiftLocked = $state(false);
  let shiftBaseStart = $state<string | null>(null);
  let shiftBaseEnd = $state<string | null>(null);
  let endDateAdjustedHint = $state('');
  let customRepeatOption = $state<{ value: string; label: string } | null>(null);
  let customAlertOption = $state<{ value: string; label: string } | null>(null);
  let fetchedEventId = $state<string | null>(null);

  const editingId = $derived(app.editingId);
  const isReadOnlyEvent = $derived(Boolean(editingId && sourceTypes[(sourceId.split('::')[0] || sourceId)] === 'ics_url'));

  function setAlertMinutes(minutes: number[] | null | undefined) {
    const state = buildAlertSelectState(minutes, alertOptions);
    alertMinutesBefore = state.minutes;
    alertSelectValue = state.selectValue;
    customAlertOption = state.customOption;
  }

  $effect(() => {
    const tz = app.timezone || undefined;
    if (saving || deleting || isReadOnlyEvent) return;

    if (editingId) {
      const prefill = initialEvent?.id === editingId ? initialEvent : null;
      if (prefill) {
        fetchedEventId = editingId;
        title = prefill.title;
        start = toLocalDatetimeInput(prefill.start, tz);
        end = toLocalDatetimeInput(prefill.end, tz);
        allDay = prefill.all_day;
        description = prefill.description ?? '';
        location = prefill.location ?? '';
        recurrence = prefill.recurrence ?? '';
        sourceId = prefill.source_id;
        setAlertMinutes(prefill.alert_minutes_before);
        shiftHuman = '';
        shiftDeltaSeconds = 0;
        shiftDeltaLabel = '';
        shiftLocked = false;
        shiftBaseStart = null;
        shiftBaseEnd = null;
      } else {
        if (fetchedEventId === editingId) return;
        fetchedEventId = editingId;
        const currentId = editingId;
        getEvent(currentId).then((e) => {
          if (editingId !== currentId) return;
          title = e.title;
          start = toLocalDatetimeInput(e.start, tz);
          end = toLocalDatetimeInput(e.end, tz);
          allDay = e.all_day;
          description = e.description ?? '';
          location = e.location ?? '';
          recurrence = e.recurrence ?? '';
          sourceId = e.source_id;
          setAlertMinutes(e.alert_minutes_before);
          shiftHuman = '';
          shiftDeltaSeconds = 0;
          shiftDeltaLabel = '';
          shiftLocked = false;
          shiftBaseStart = null;
          shiftBaseEnd = null;
        }).catch((err) => {
          if (editingId !== currentId || deleting) return;
          error = err instanceof Error ? err.message : 'Failed to load event';
        });
      }
    } else {
      fetchedEventId = null;
      const d = app.selectedDate;
      title = '';
      start = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T09:00`;
      end = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T10:00`;
      allDay = false;
      description = '';
      location = '';
      recurrence = '';
      setAlertMinutes(null);
      shiftHuman = '';
      shiftDeltaSeconds = 0;
      shiftDeltaLabel = '';
      shiftLocked = false;
      shiftBaseStart = null;
      shiftBaseEnd = null;
    }
  });

  onMount(() => {
    getSources().then((allSources) => {
      sourceTypes = Object.fromEntries(allSources.map((source) => [source.id, source.type]));
      sources = allSources
        .filter((source) => source.type === 'local_folder' || source.type === 'caldav')
        .map((source) => ({ id: source.id, name: source.name, type: source.type }));
      if (sources.length && !editingId) sourceId = sources[0].id;
    });
  });

  async function submit() {
    if (saving || deleting) return;
    error = '';
    if (!title.trim()) {
      error = 'Title is required';
      return;
    }
    if (!editingId && !sourceId) {
      error = 'Select a calendar source';
      return;
    }

    const currentEditingId = editingId;
    const startIso = new Date(start).toISOString();
    const endIso = new Date(end).toISOString();
    const resolvedAlertMinutes = resolveAlertMinutesForSave();
    const payload = {
      title: title.trim(),
      start: startIso,
      end: endIso,
      all_day: allDay,
      description: description || null,
      location: location.trim() || null,
      recurrence: recurrence || null,
      alert_minutes_before: resolvedAlertMinutes.length ? resolvedAlertMinutes : null,
    };

    saving = true;
    try {
      let saved: { id: string; start: string; title: string } | undefined;
      if (currentEditingId) {
        await updateEvent(currentEditingId, payload);
      } else {
        const created = await createEvent({ source_id: sourceId, ...payload });
        saved = { id: created.id, start: created.start, title: created.title };
      }
      await onsave(saved);
      onclose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to save';
    } finally {
      saving = false;
    }
  }

  async function performDelete() {
    if (!editingId || deleting || saving) return;
    deleting = true;
    error = '';
    try {
      await deleteEvent(editingId);
      await onsave();
      onclose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to delete';
    } finally {
      deleting = false;
    }
  }

  let modalEl: HTMLDivElement | undefined;
  let titleEl: HTMLInputElement | undefined;
  let startEl: HTMLInputElement | undefined;
  let endEl: HTMLInputElement | undefined;
  let startHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let endHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let allDayEl: HTMLInputElement | undefined;
  let locationEl: HTMLInputElement | undefined;
  let recurrenceEl: HTMLSelectElement | undefined;
  let alertEl: HTMLSelectElement | undefined;
  let alertHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let repeatHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let shiftHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let descriptionEl: HTMLTextAreaElement | undefined;
  let sourceIdEl = $state<HTMLSelectElement | undefined>(undefined);

  $effect(() => {
    if (app.modalOpen === 'event') {
      tick().then(() => {
        if (editingId) modalEl?.focus();
        else titleEl?.focus();
      });
    }
  });

  function cycleSelect(sel: HTMLSelectElement, dir: 1 | -1) {
    cycleSelectOption(sel, dir);
  }

  function parseTimezone(): string | undefined {
    return getPreferredTimezone(app.timezone);
  }

  function addOneDay(localDatetime: string): string {
    const [datePart, timePart = '00:00'] = localDatetime.split('T');
    const [year, month, day] = datePart.split('-').map(Number);
    const [hour, minute] = timePart.split(':').map(Number);
    const d = new Date(year, (month ?? 1) - 1, day ?? 1, hour ?? 0, minute ?? 0);
    d.setDate(d.getDate() + 1);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const h = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${dd}T${h}:${min}`;
  }

  function shiftLocalDatetime(localDatetime: string, seconds: number): string {
    const shifted = new Date(new Date(localDatetime).getTime() + seconds * 1000);
    const y = shifted.getFullYear();
    const m = String(shifted.getMonth() + 1).padStart(2, '0');
    const d = String(shifted.getDate()).padStart(2, '0');
    const h = String(shifted.getHours()).padStart(2, '0');
    const min = String(shifted.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${d}T${h}:${min}`;
  }

  async function applyHumanDate(field: 'start' | 'end'): Promise<boolean> {
    const text = (field === 'start' ? startHuman : endHuman).trim();
    if (!text) return false;
    error = '';
    endDateAdjustedHint = '';
    try {
      const contextLocal = field === 'end' ? (start || end || undefined) : (start || undefined);
      const parsed = await parseHumanDatetime(text, parseTimezone(), contextLocal);
      let localValue = toLocalDatetimeInput(parsed.iso, app.timezone || undefined);

      if (field === 'end' && !parsed.hasDate && start && localValue <= start) {
        localValue = addOneDay(localValue);
        endDateAdjustedHint = 'Adjusted to next day to keep end after start.';
      }

      if (field === 'start') {
        start = localValue;
      } else {
        end = localValue;
      }
      return true;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to parse date/time';
      return false;
    }
  }

  function clearActiveDateFieldIfNeeded(field: 'start' | 'end') {
    clearIfFocusOutside(field === 'start' ? [startEl, startHumanEl] : [endEl, endHumanEl], () => {
      if (activeDateField === field) activeDateField = null;
    });
  }

  function focusHumanDateField(field: 'start' | 'end') {
    activateAndFocus(
      () => {
        activeDateField = field;
      },
      () => (field === 'start' ? startHumanEl : endHumanEl),
    );
  }

  function clearRepeatFieldIfNeeded() {
    clearIfFocusOutside([recurrenceEl, repeatHumanEl], () => {
      activeRepeatField = false;
    });
  }

  function focusRepeatHumanField() {
    activateAndFocus(
      () => {
        activeRepeatField = true;
      },
      () => repeatHumanEl,
    );
  }

  function clearAlertFieldIfNeeded() {
    clearIfFocusOutside([alertEl, alertHumanEl], () => {
      activeAlertField = false;
    });
  }

  function focusAlertHumanField() {
    activateAndFocus(
      () => {
        activeAlertField = true;
      },
      () => alertHumanEl,
    );
  }

  async function applyHumanRepeat(): Promise<boolean> {
    const text = repeatHuman.trim();
    if (!text) return false;
    error = '';
    try {
      const parsed = await parseHumanRecurrence(text);
      customRepeatOption = { value: parsed.rrule, label: parsed.label };
      recurrence = parsed.rrule;
      activeRepeatField = false;
      blurInputAndFocusModal(repeatHumanEl, modalEl);
      return true;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to parse recurrence';
      return false;
    }
  }

  async function applyHumanAlerts(): Promise<boolean> {
    const text = alertHuman.trim();
    if (!text) return false;
    error = '';
    try {
      const parsed = await parseHumanAlerts(text);
      setAlertMinutes(parsed.minutes);
      return true;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to parse alerts';
      return false;
    }
  }

  async function applyHumanShift(): Promise<boolean> {
    const text = shiftHuman.trim();
    if (!text) return false;
    error = '';
    try {
      const parsed = await parseHumanDelta(text);
      const baseStart = shiftBaseStart ?? start;
      const baseEnd = shiftBaseEnd ?? end;
      shiftBaseStart = baseStart;
      shiftBaseEnd = baseEnd;
      shiftDeltaSeconds = parsed.seconds;
      shiftDeltaLabel = parsed.label;
      shiftHuman = parsed.label;
      start = shiftLocalDatetime(baseStart, parsed.seconds);
      end = shiftLocalDatetime(baseEnd, parsed.seconds);
      shiftLocked = true;
      activeDateField = null;
      blurInputAndFocusModal(shiftHumanEl, modalEl);
      return true;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to parse shift';
      return false;
    }
  }

  function handleShiftInput() {
    if (!shiftLocked) return;
    shiftLocked = false;
    shiftDeltaSeconds = 0;
    shiftDeltaLabel = '';
    if (shiftBaseStart && shiftBaseEnd) {
      start = shiftBaseStart;
      end = shiftBaseEnd;
    }
  }

  function onStartInput() {
    if (!shiftLocked) {
      shiftBaseStart = null;
      shiftBaseEnd = null;
    }
  }

  function onEndInput() {
    if (!shiftLocked) {
      shiftBaseStart = null;
      shiftBaseEnd = null;
    }
  }

  function applyAlertSelect() {
    const resolved = resolveAlertMinutesFromSelection(alertSelectValue);
    if (resolved !== null) setAlertMinutes(resolved);
  }

  function resolveAlertMinutesForSave(): number[] {
    return resolveAlertMinutesForSubmit(alertSelectValue, alertMinutesBefore);
  }

  function handleKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement;
    const inDateInput = target === startEl || target === endEl;
    const inTextInput = isTextInputTarget(target);

    if (e.key === 'Enter' && target === startHumanEl) {
      e.preventDefault();
      void applyHumanDate('start').then((ok) => {
        if (!ok) return;
        focusHumanDateField('end');
      });
      return;
    }
    if (e.key === 'Enter' && target === endHumanEl) {
      e.preventDefault();
      void applyHumanDate('end').then((ok) => {
        if (!ok) return;
        activeDateField = null;
        blurInputAndFocusModal(endHumanEl, modalEl);
      });
      return;
    }
    if (e.key === 'Enter' && target === repeatHumanEl) {
      e.preventDefault();
      void applyHumanRepeat();
      return;
    }
    if (e.key === 'Enter' && target === alertHumanEl) {
      e.preventDefault();
      void applyHumanAlerts().then((ok) => {
        if (!ok) return;
        activeAlertField = false;
        blurInputAndFocusModal(alertHumanEl, modalEl);
      });
      return;
    }
    if (e.key === 'Enter' && target === shiftHumanEl) {
      e.preventDefault();
      void applyHumanShift();
      return;
    }
    if (inDateInput && e.key.toLowerCase() === 'h') {
      if (shiftLocked) return;
      e.preventDefault();
      if (target === startEl) {
        focusHumanDateField('start');
      } else if (target === endEl) {
        focusHumanDateField('end');
      }
      return;
    }
    if (target === recurrenceEl && e.key.toLowerCase() === 'h') {
      e.preventDefault();
      focusRepeatHumanField();
      return;
    }
    if (target === alertEl && e.key.toLowerCase() === 'h') {
      e.preventDefault();
      focusAlertHumanField();
      return;
    }
    if (handleCommonModalKeydown({
      event: e,
      target,
      isTextInput: inTextInput,
      modalEl,
      onClose: onclose,
      onSubmit: isReadOnlyEvent ? () => {} : submit,
      cycleSelect,
      onTextInputEscape: (activeTarget) => {
        if (activeTarget === startHumanEl || activeTarget === endHumanEl) activeDateField = null;
        if (activeTarget === repeatHumanEl) activeRepeatField = false;
        if (activeTarget === alertHumanEl) activeAlertField = false;
      },
      deleteConfirmMessage: editingId && !isReadOnlyEvent ? 'Delete this event?' : undefined,
      onDelete: editingId && !isReadOnlyEvent ? () => { void performDelete(); } : undefined,
    })) {
      return;
    }

    if (isReadOnlyEvent) return;

    if (inTextInput) return;

    const key = e.key.toLowerCase();
    if (key === 't') {
      e.preventDefault();
      titleEl?.focus();
    } else if (key === 's') {
      if (shiftLocked) return;
      e.preventDefault();
      focusHumanDateField('start');
    } else if (key === 'e') {
      if (shiftLocked) return;
      e.preventDefault();
      focusHumanDateField('end');
    } else if (key === 'f') {
      e.preventDefault();
      shiftHumanEl?.focus();
    } else if (key === 'a') {
      e.preventDefault();
      allDayEl?.focus();
    } else if (key === 'l') {
      e.preventDefault();
      locationEl?.focus();
    } else if (key === 'r') {
      e.preventDefault();
      recurrenceEl?.focus();
    } else if (key === 'n') {
      e.preventDefault();
      alertEl?.focus();
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
    {#if deleting}
      <p class="modal-loading flex items-center gap-2 text-[var(--text-muted)]" aria-busy="true" aria-live="polite">
        <span class="todo-loading-spinner" aria-hidden="true"></span>
        Deleting…
      </p>
    {/if}
    {#if saving}
      <p class="modal-loading flex items-center gap-2 text-[var(--text-muted)]" aria-busy="true" aria-live="polite">
        <span class="todo-loading-spinner" aria-hidden="true"></span>
        {editingId ? 'Saving…' : 'Creating…'}
      </p>
    {/if}
    <fieldset class="modal-fields" class:is-read-only={isReadOnlyEvent} disabled={isReadOnlyEvent}>
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
      <input
        type="datetime-local"
        bind:value={start}
        disabled={allDay || shiftLocked}
        class:opacity-60={allDay || shiftLocked}
        class:bg-[var(--bg-subtle)]={allDay || shiftLocked}
        bind:this={startEl}
        oninput={onStartInput}
        onfocus={() => { activeDateField = 'start'; }}
        onblur={() => clearActiveDateFieldIfNeeded('start')}
      />
    </div>
      {#if activeDateField === 'start'}
        <div class="form-row">
        <div class="form-row-header">
          <span class="field-label">Human-friendly</span>
          <span class="field-shortcut">H</span>
        </div>
        <input
          type="text"
          bind:value={startHuman}
          bind:this={startHumanEl}
          placeholder="e.g. tomorrow 9am"
          disabled={shiftLocked}
          class:opacity-60={shiftLocked}
          class:bg-[var(--bg-subtle)]={shiftLocked}
          onfocus={() => { activeDateField = 'start'; }}
          onblur={() => clearActiveDateFieldIfNeeded('start')}
        />
        </div>
      {/if}
      <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">End</span>
        <span class="field-shortcut">E</span>
      </div>
      <input
        type="datetime-local"
        bind:value={end}
        disabled={allDay || shiftLocked}
        class:opacity-60={allDay || shiftLocked}
        class:bg-[var(--bg-subtle)]={allDay || shiftLocked}
        bind:this={endEl}
        oninput={onEndInput}
        onfocus={() => { activeDateField = 'end'; }}
        onblur={() => clearActiveDateFieldIfNeeded('end')}
      />
    </div>
      {#if activeDateField === 'end'}
        <div class="form-row">
        <div class="form-row-header">
          <span class="field-label">Human-friendly</span>
          <span class="field-shortcut">H</span>
        </div>
        <input
          type="text"
          bind:value={endHuman}
          bind:this={endHumanEl}
          placeholder="e.g. tomorrow 10am"
          disabled={shiftLocked}
          class:opacity-60={shiftLocked}
          class:bg-[var(--bg-subtle)]={shiftLocked}
          onfocus={() => { activeDateField = 'end'; }}
          onblur={() => clearActiveDateFieldIfNeeded('end')}
        />
        {#if endDateAdjustedHint}
          <p class="text-sm text-[var(--text-muted)] mt-1">{endDateAdjustedHint}</p>
        {/if}
        </div>
      {/if}
      <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Shift by</span>
        <span class="field-shortcut">F</span>
      </div>
      <input
        type="text"
        bind:value={shiftHuman}
        bind:this={shiftHumanEl}
        placeholder="e.g. +2h 30m or -1 day"
        title={shiftLocked ? `Locked: ${shiftDeltaLabel}` : undefined}
        oninput={handleShiftInput}
      />
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
      <select
        bind:value={recurrence}
        bind:this={recurrenceEl}
        onfocus={() => { activeRepeatField = true; }}
        onblur={clearRepeatFieldIfNeeded}
      >
        {#each repeatOptions as opt}
          <option value={opt.value}>{opt.label}</option>
        {/each}
        {#if customRepeatOption && !repeatOptions.some((opt) => opt.value === customRepeatOption?.value)}
          <option value={customRepeatOption.value}>{customRepeatOption.label}</option>
        {/if}
      </select>
    </div>
      {#if activeRepeatField}
        <div class="form-row">
        <div class="form-row-header">
          <span class="field-label">Human-friendly</span>
          <span class="field-shortcut">H</span>
        </div>
        <div class="repeat-human-input">
          <span class="repeat-human-prefix">Every</span>
          <input
            type="text"
            bind:value={repeatHuman}
            bind:this={repeatHumanEl}
            placeholder="e.g. 2 weeks"
            onfocus={() => { activeRepeatField = true; }}
            onblur={clearRepeatFieldIfNeeded}
          />
        </div>
        </div>
      {/if}
      <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Alert</span>
        <span class="field-shortcut">N</span>
      </div>
      <select
        bind:value={alertSelectValue}
        bind:this={alertEl}
        onfocus={() => { activeAlertField = true; }}
        onblur={clearAlertFieldIfNeeded}
        onchange={applyAlertSelect}
      >
        {#each alertOptions as opt}
          <option value={opt.value}>{opt.label}</option>
        {/each}
        {#if customAlertOption}
          <option value={customAlertOption.value}>{customAlertOption.label}</option>
        {/if}
      </select>
    </div>
      {#if activeAlertField}
        <div class="form-row">
        <div class="form-row-header">
          <span class="field-label">Human-friendly</span>
          <span class="field-shortcut">H</span>
        </div>
        <input
          type="text"
          bind:value={alertHuman}
          bind:this={alertHumanEl}
          placeholder="e.g. 10m before, 1h before (comma-separated)"
          onfocus={() => { activeAlertField = true; }}
          onblur={clearAlertFieldIfNeeded}
        />
        </div>
      {/if}
      <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Description</span>
        <span class="field-shortcut">D</span>
      </div>
      <textarea bind:value={description} rows="3" bind:this={descriptionEl}></textarea>
      </div>
    </fieldset>
    <div class="form-actions">
      {#if !isReadOnlyEvent}
        <div class="form-action-with-hint">
          <button class="btn btn-primary" onclick={submit} disabled={saving || deleting}>Save</button>
          <span class="action-hint">Ctrl+Enter</span>
        </div>
      {/if}
      {#if editingId && !isReadOnlyEvent}
        <div class="form-action-with-hint">
          <button
            class="btn btn-ghost"
            type="button"
            disabled={saving || deleting}
            onclick={async () => {
              if (!confirm('Delete this event?')) return;
              void performDelete();
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
