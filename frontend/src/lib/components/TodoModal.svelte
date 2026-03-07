<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { createTodo, updateTodo, getTodo, getSources, deleteTodo, parseHumanDatetime, parseHumanRecurrence, parseHumanAlerts } from '$lib/api';
  import type { Todo, TodoCreate, TodoUpdate } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { toLocalDatetimeInput } from '$lib/date';

  interface Props {
    todoId: string | null;
    initialTodo?: Todo | null;
    onclose: () => void;
    onsave: () => void | Promise<void>;
  }

  let { todoId, initialTodo = null, onclose, onsave }: Props = $props();

  let summary = $state('');
  let completed = $state(false);
  let due = $state('');
  let description = $state('');
  let recurrence = $state('');
  let alertMinutesBefore = $state<number[]>([]);
  let alertSelectValue = $state('');
  let sourceId = $state('');
  let sources = $state<{ id: string; name: string; type: string }[]>([]);
  let error = $state('');
  let saving = $state(false);
  let deleting = $state(false);
  let activeDueField = $state(false);
  let activeRepeatField = $state(false);
  let activeAlertField = $state(false);
  let dueHuman = $state('');
  let repeatHuman = $state('');
  let alertHuman = $state('');
  let customRepeatOption = $state<{ value: string; label: string } | null>(null);
  let customAlertOption = $state<{ value: string; label: string } | null>(null);
  let fetchedTodoId = $state<string | null>(null);

  const repeatOptions = [
    { value: '', label: 'None' },
    { value: 'FREQ=DAILY', label: 'Daily' },
    { value: 'FREQ=WEEKLY', label: 'Weekly' },
    { value: 'FREQ=MONTHLY', label: 'Monthly' },
    { value: 'FREQ=YEARLY', label: 'Yearly' },
  ];
  const alertOptions = [
    { value: '', label: 'None' },
    { value: '0', label: 'At time' },
    { value: '5', label: '5 minutes before' },
    { value: '10', label: '10 minutes before' },
    { value: '15', label: '15 minutes before' },
    { value: '30', label: '30 minutes before' },
    { value: '60', label: '1 hour before' },
    { value: '120', label: '2 hours before' },
    { value: '1440', label: '1 day before' },
  ];

  function formatAlertLabel(minutes: number[]): string {
    return minutes.map((m) => {
      if (m === 0) return 'at time';
      if (m % 1440 === 0) return `${m / 1440}d before`;
      if (m % 60 === 0) return `${m / 60}h before`;
      return `${m}m before`;
    }).join(', ');
  }

  function setAlertMinutes(minutes: number[] | null | undefined) {
    const normalized = Array.from(new Set((minutes ?? []).map((m) => Math.max(0, Number(m))))).sort((a, b) => a - b);
    alertMinutesBefore = normalized;
    if (!normalized.length) {
      customAlertOption = null;
      alertSelectValue = '';
      return;
    }
    if (normalized.length === 1 && alertOptions.some((opt) => opt.value === String(normalized[0]))) {
      customAlertOption = null;
      alertSelectValue = String(normalized[0]);
      return;
    }
    const value = `custom:${normalized.join(',')}`;
    customAlertOption = { value, label: `Custom (${formatAlertLabel(normalized)})` };
    alertSelectValue = value;
  }

  const isInstance = $derived(todoId ? todoId.split('::').length >= 4 : false);

  $effect(() => {
    const tz = app.timezone || undefined;
    if (saving || deleting) return;

    if (todoId) {
      if (initialTodo && initialTodo.id === todoId) {
        fetchedTodoId = todoId;
        summary = initialTodo.summary;
        completed = initialTodo.completed;
        due = initialTodo.due ? toLocalDatetimeInput(initialTodo.due, tz) : '';
        description = initialTodo.description ?? '';
        recurrence = initialTodo.recurrence ?? '';
        setAlertMinutes(initialTodo.alert_minutes_before);
        return;
      }
      if (fetchedTodoId === todoId) return;
      fetchedTodoId = todoId;
      const currentId = todoId;
      getTodo(currentId).then((t) => {
        if (todoId !== currentId) return;
        summary = t.summary;
        completed = t.completed;
        due = t.due ? toLocalDatetimeInput(t.due, tz) : '';
        description = t.description ?? '';
        recurrence = t.recurrence ?? '';
        setAlertMinutes(t.alert_minutes_before);
      }).catch((e) => {
        if (todoId !== currentId || deleting) return;
        error = e instanceof Error ? e.message : 'Failed to load todo';
      });
    } else {
      fetchedTodoId = null;
      recurrence = '';
      setAlertMinutes(null);
    }
  });

  onMount(() => {
    getSources().then((s) => {
      sources = s.filter((x) => x.type === 'local_folder' || x.type === 'caldav').map((x) => ({ id: x.id, name: x.name, type: x.type }));
      if (sources.length && !todoId) sourceId = sources[0].id;
    });
  });

  async function submit() {
    if (saving || deleting) return;
    error = '';
    if (!summary.trim()) {
      error = 'Summary is required';
      return;
    }
    if (!todoId && !sourceId) {
      error = 'Select a todo source';
      return;
    }

    const currentTodoId = todoId;
    const resolvedAlertMinutes = resolveAlertMinutesForSubmit();
    const payload = {
      summary: summary.trim(),
      completed,
      due: due ? new Date(due).toISOString() : null,
      description: description || null,
      recurrence: recurrence || null,
      alert_minutes_before: resolvedAlertMinutes.length ? resolvedAlertMinutes : null,
    };

    saving = true;
    try {
      if (currentTodoId) {
        await updateTodo(currentTodoId, payload);
      } else {
        await createTodo({ source_id: sourceId, ...payload });
      }
      await onsave();
      onclose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to save';
    } finally {
      saving = false;
    }
  }

  async function performDelete() {
    if (!todoId || deleting || saving) return;
    deleting = true;
    error = '';
    try {
      await deleteTodo(todoId);
      await onsave();
      onclose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to delete';
    } finally {
      deleting = false;
    }
  }

  let modalEl: HTMLDivElement | undefined;
  let summaryEl: HTMLInputElement | undefined;
  let completedEl: HTMLInputElement | undefined;
  let dueEl: HTMLInputElement | undefined;
  let dueHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let descriptionEl: HTMLTextAreaElement | undefined;
  let recurrenceEl: HTMLSelectElement | undefined;
  let alertEl: HTMLSelectElement | undefined;
  let alertHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let repeatHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let sourceIdEl: HTMLSelectElement | undefined;

  $effect(() => {
    if (app.modalOpen === 'todo') {
      tick().then(() => {
        if (todoId) modalEl?.focus();
        else summaryEl?.focus();
      });
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

  function parseTimezone(): string | undefined {
    return app.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  }

  function localNowInput(): string {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    const h = String(now.getHours()).padStart(2, '0');
    const min = String(now.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${d}T${h}:${min}`;
  }

  async function applyHumanDue(): Promise<boolean> {
    const text = dueHuman.trim();
    if (!text) return false;
    error = '';
    try {
      const contextLocal = due || localNowInput();
      const parsed = await parseHumanDatetime(text, parseTimezone(), contextLocal);
      due = toLocalDatetimeInput(parsed.iso, app.timezone || undefined);
      return true;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to parse date/time';
      return false;
    }
  }

  function clearDueFieldIfNeeded() {
    tick().then(() => {
      const active = document.activeElement;
      if (active !== dueEl && active !== dueHumanEl) activeDueField = false;
    });
  }

  function focusDueHumanField() {
    activeDueField = true;
    tick().then(() => dueHumanEl?.focus());
  }

  function clearRepeatFieldIfNeeded() {
    tick().then(() => {
      const active = document.activeElement;
      if (active !== recurrenceEl && active !== repeatHumanEl) activeRepeatField = false;
    });
  }

  function focusRepeatHumanField() {
    activeRepeatField = true;
    tick().then(() => repeatHumanEl?.focus());
  }

  function clearAlertFieldIfNeeded() {
    tick().then(() => {
      const active = document.activeElement;
      if (active !== alertEl && active !== alertHumanEl) activeAlertField = false;
    });
  }

  function focusAlertHumanField() {
    activeAlertField = true;
    tick().then(() => alertHumanEl?.focus());
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
      repeatHumanEl?.blur();
      modalEl?.focus();
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

  function applyAlertSelect() {
    if (!alertSelectValue) {
      setAlertMinutes([]);
      return;
    }
    if (alertSelectValue.startsWith('custom:')) return;
    const v = Number(alertSelectValue);
    if (Number.isFinite(v)) setAlertMinutes([v]);
  }

  function resolveAlertMinutesForSubmit(): number[] {
    if (alertSelectValue && !alertSelectValue.startsWith('custom:')) {
      const v = Number(alertSelectValue);
      if (Number.isFinite(v)) return [Math.max(0, Math.trunc(v))];
    }
    return alertMinutesBefore;
  }

  function handleKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement;
    const inHumanInput = target === dueHumanEl || target === repeatHumanEl || target === alertHumanEl;
    const inTextInput = target instanceof HTMLInputElement && target.type !== 'checkbox' && target.type !== 'radio'
      || target instanceof HTMLTextAreaElement;

    if (e.key === 'Escape') {
      if (inTextInput) {
        e.preventDefault();
        if (target === dueHumanEl) activeDueField = false;
        if (target === repeatHumanEl) activeRepeatField = false;
        if (target === alertHumanEl) activeAlertField = false;
        target.blur();
        modalEl?.focus();
      } else {
        onclose();
      }
      return;
    }
    if (e.key === 'Enter' && target === dueHumanEl) {
      e.preventDefault();
      void applyHumanDue().then((ok) => {
        if (!ok) return;
        activeDueField = false;
        dueHumanEl?.blur();
        modalEl?.focus();
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
        alertHumanEl?.blur();
        modalEl?.focus();
      });
      return;
    }
    if (target === dueEl && e.key.toLowerCase() === 'h') {
      e.preventDefault();
      focusDueHumanField();
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
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      submit();
      return;
    }
    if (todoId && e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'd') {
      e.preventDefault();
      if (confirm('Delete this todo?')) {
        void performDelete();
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
    if (!inTextInput && !e.shiftKey && (e.key === 'j' || e.key === 'k')) {
      e.preventDefault();
      if (modalEl) modalEl.scrollTop += e.key === 'j' ? 60 : -60;
      return;
    }
    if (inTextInput) return;

    const key = e.key.toLowerCase();
    if (key === 's') {
      e.preventDefault();
      summaryEl?.focus();
    } else if (key === 'c') {
      e.preventDefault();
      completedEl?.focus();
    } else if (key === 'u') {
      e.preventDefault();
      focusDueHumanField();
    } else if (key === 'd') {
      e.preventDefault();
      descriptionEl?.focus();
    } else if (key === 'r') {
      e.preventDefault();
      recurrenceEl?.focus();
    } else if (key === 'n') {
      e.preventDefault();
      alertEl?.focus();
    } else if (key === 'l' && sourceIdEl) {
      e.preventDefault();
      sourceIdEl.focus();
    }
  }
</script>

<div class="modal-backdrop" role="dialog" aria-modal="true" onkeydown={handleKeydown} onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="modal" tabindex="-1" bind:this={modalEl} onclick={(e) => e.stopPropagation()}>
    <h2>{todoId ? 'Edit todo' : 'New todo'}</h2>
    {#if deleting}
      <p class="modal-loading flex items-center gap-2 text-[var(--text-muted)]" aria-busy="true" aria-live="polite">
        <span class="todo-loading-spinner" aria-hidden="true"></span>
        Deleting…
      </p>
    {/if}
    {#if saving}
      <p class="modal-loading flex items-center gap-2 text-[var(--text-muted)]" aria-busy="true" aria-live="polite">
        <span class="todo-loading-spinner" aria-hidden="true"></span>
        {todoId ? 'Saving…' : 'Creating…'}
      </p>
    {/if}
    {#if error}
      <p class="text-red-600 text-sm">{error}</p>
    {/if}
    {#if !todoId}
      <div class="form-row">
        <div class="form-row-header">
          <span class="field-label">List</span>
          <span class="field-shortcut">L</span>
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
        <span class="field-label">Summary</span>
        <span class="field-shortcut">S</span>
      </div>
      <input type="text" bind:value={summary} bind:this={summaryEl} />
    </div>
    <div class="form-row form-row-checkbox">
      <div class="form-row-header">
        <span class="field-label">Completed</span>
        <span class="field-shortcut">C</span>
      </div>
      <label class="checkbox-label">
        <input type="checkbox" bind:checked={completed} bind:this={completedEl} />
      </label>
    </div>
    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Due date</span>
        <span class="field-shortcut">U</span>
      </div>
      <input
        type="datetime-local"
        bind:value={due}
        bind:this={dueEl}
        onfocus={() => { activeDueField = true; }}
        onblur={clearDueFieldIfNeeded}
      />
    </div>
    {#if activeDueField}
      <div class="form-row">
        <div class="form-row-header">
          <span class="field-label">Human-friendly</span>
          <span class="field-shortcut">H</span>
        </div>
        <input
          type="text"
          bind:value={dueHuman}
          bind:this={dueHumanEl}
          placeholder="e.g. next friday 5pm"
          onfocus={() => { activeDueField = true; }}
          onblur={clearDueFieldIfNeeded}
        />
      </div>
    {/if}
    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Repeat</span>
        <span class="field-shortcut">R</span>
      </div>
      <select
        bind:value={recurrence}
        bind:this={recurrenceEl}
        disabled={isInstance}
        title={isInstance ? 'Repeat is set on the series' : undefined}
        onfocus={() => { if (!isInstance) activeRepeatField = true; }}
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
    {#if activeRepeatField && !isInstance}
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
            placeholder="e.g. 3 days"
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
    <div class="form-actions">
      <div class="form-action-with-hint">
        <button class="btn btn-primary" onclick={submit} disabled={saving || deleting}>Save</button>
        <span class="action-hint">Ctrl+Enter</span>
      </div>
      {#if todoId}
        <div class="form-action-with-hint">
          <button
            class="btn btn-ghost"
            type="button"
            disabled={saving || deleting}
            onclick={() => {
              if (!confirm('Delete this todo?')) return;
              void performDelete();
            }}
          >Delete</button>
          <span class="action-hint">Ctrl+Shift+D</span>
        </div>
      {/if}
      <div class="form-action-with-hint">
        <button class="btn btn-ghost" onclick={onclose} type="button" disabled={deleting}>Cancel</button>
        <span class="action-hint">Esc</span>
      </div>
    </div>
  </div>
</div>
