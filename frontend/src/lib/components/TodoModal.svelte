<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { createTodo, updateTodo, getTodo, getWritableSources, deleteTodo, parseHumanDatetime, parseHumanRecurrence, parseHumanAlerts, parseHumanDelta } from '$lib/api';
  import type { Todo } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { toLocalDatetimeInput } from '$lib/date';
  import {
    alertOptions,
    buildAlertSelectState,
    cycleSelectOption,
    getPreferredTimezone,
    localNowInput,
    repeatOptions,
    resolveAlertMinutesFromSelection,
    resolveAlertMinutesForSubmit,
  } from '$lib/modal-utils';
  import { handleCommonModalKeydown, isTextInputTarget } from '$lib/modal-keyboard';
  import { activateAndFocus, blurInputAndFocusModal, clearIfFocusOutside } from '$lib/modal-focus';

  interface Props {
    todoId: string | null;
    initialTodo?: Todo | null;
    existingCategories?: string[];
    onclose: () => void;
    onsave: () => void | Promise<void>;
  }

  let { todoId, initialTodo = null, existingCategories = [], onclose, onsave }: Props = $props();

  let summary = $state('');
  let categoryText = $state('');
  let categorySuggestion = $state('');
  let categorySuggestionGhostPrefix = $state('');
  let categorySuggestionGhostSuffix = $state('');
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
  let shiftHuman = $state('');
  let shiftDeltaSeconds = $state(0);
  let shiftDeltaLabel = $state('');
  let shiftLocked = $state(false);
  let shiftBaseDue = $state<string | null>(null);
  let customRepeatOption = $state<{ value: string; label: string } | null>(null);
  let customAlertOption = $state<{ value: string; label: string } | null>(null);
  let fetchedTodoId = $state<string | null>(null);

  function setAlertMinutes(minutes: number[] | null | undefined) {
    const state = buildAlertSelectState(minutes, alertOptions);
    alertMinutesBefore = state.minutes;
    alertSelectValue = state.selectValue;
    customAlertOption = state.customOption;
  }

  function normalizeCategory(value: string): string {
    return value.trim().replace(/\s+/g, ' ');
  }

  function normalizeCategoriesFromText(text: string): string[] | null {
    const seen = new Set<string>();
    const parsed: string[] = [];
    for (const part of text.split(',')) {
      const normalized = normalizeCategory(part);
      if (!normalized) continue;
      const key = normalized.toLocaleLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      parsed.push(normalized);
    }
    return parsed.length > 0 ? parsed : null;
  }

  const normalizedExistingCategories = $derived.by(() => {
    const map = new Map<string, string>();
    for (const category of existingCategories) {
      const normalized = normalizeCategory(category);
      if (!normalized) continue;
      const key = normalized.toLocaleLowerCase();
      if (!map.has(key)) map.set(key, normalized);
    }
    return [...map.values()].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
  });

  const isInstance = $derived(todoId ? todoId.split('::').length >= 4 : false);

  $effect(() => {
    const tz = app.timezone || undefined;
    if (saving || deleting) return;

    if (todoId) {
      if (initialTodo && initialTodo.id === todoId) {
        fetchedTodoId = todoId;
        summary = initialTodo.summary;
        categoryText = (initialTodo.categories ?? []).join(', ');
        completed = initialTodo.completed;
        due = initialTodo.due ? toLocalDatetimeInput(initialTodo.due, tz) : '';
        description = initialTodo.description ?? '';
        recurrence = initialTodo.recurrence ?? '';
        setAlertMinutes(initialTodo.alert_minutes_before);
        shiftHuman = '';
        shiftDeltaSeconds = 0;
        shiftDeltaLabel = '';
        shiftLocked = false;
        shiftBaseDue = null;
        return;
      }
      if (fetchedTodoId === todoId) return;
      fetchedTodoId = todoId;
      const currentId = todoId;
      getTodo(currentId).then((t) => {
        if (todoId !== currentId) return;
        summary = t.summary;
        categoryText = (t.categories ?? []).join(', ');
        completed = t.completed;
        due = t.due ? toLocalDatetimeInput(t.due, tz) : '';
        description = t.description ?? '';
        recurrence = t.recurrence ?? '';
        setAlertMinutes(t.alert_minutes_before);
        shiftHuman = '';
        shiftDeltaSeconds = 0;
        shiftDeltaLabel = '';
        shiftLocked = false;
        shiftBaseDue = null;
      }).catch((e) => {
        if (todoId !== currentId || deleting) return;
        error = e instanceof Error ? e.message : 'Failed to load todo';
      });
    } else {
      fetchedTodoId = null;
      categoryText = '';
      recurrence = '';
      setAlertMinutes(null);
      shiftHuman = '';
      shiftDeltaSeconds = 0;
      shiftDeltaLabel = '';
      shiftLocked = false;
      shiftBaseDue = null;
    }
  });

  onMount(() => {
    getWritableSources().then((s: Array<{ id: string; name: string; type: string }>) => {
      sources = s;
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
    if (shiftLocked && !due) {
      error = 'Due date is required when using Shift by';
      return;
    }

    const currentTodoId = todoId;
    const resolvedAlertMinutes = resolveAlertMinutesForSave();
    const resolvedCategories = normalizeCategoriesFromText(categoryText);
    const payload = {
      summary: summary.trim(),
      completed,
      due: due ? new Date(due).toISOString() : null,
      description: description || null,
      recurrence: recurrence || null,
      categories: resolvedCategories,
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
  let categoryEl: HTMLInputElement | undefined;
  let completedEl: HTMLInputElement | undefined;
  let dueEl: HTMLInputElement | undefined;
  let dueHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let descriptionEl: HTMLTextAreaElement | undefined;
  let recurrenceEl: HTMLSelectElement | undefined;
  let alertEl: HTMLSelectElement | undefined;
  let alertHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let repeatHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let shiftHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let sourceIdEl = $state<HTMLSelectElement | undefined>(undefined);

  function clearCategorySuggestion() {
    categorySuggestion = '';
    categorySuggestionGhostPrefix = '';
    categorySuggestionGhostSuffix = '';
  }

  function getCategoryTokenContext() {
    const input = categoryEl;
    if (!input) return null;
    const value = categoryText;
    const caret = input.selectionStart ?? value.length;
    const left = value.slice(0, caret);
    const tokenStart = left.lastIndexOf(',') + 1;
    const right = value.slice(caret);
    const nextComma = right.indexOf(',');
    const tokenEnd = nextComma === -1 ? value.length : caret + nextComma;
    const token = value.slice(tokenStart, tokenEnd);
    const leading = token.match(/^\s*/)?.[0] ?? '';
    const trailing = token.match(/\s*$/)?.[0] ?? '';
    const rawStart = tokenStart + leading.length;
    const rawEnd = tokenEnd - trailing.length;
    const typedPrefix = normalizeCategory(value.slice(rawStart, caret));
    const normalizedToken = normalizeCategory(value.slice(rawStart, rawEnd));
    return {
      value,
      caret,
      tokenStart,
      tokenEnd,
      rawStart,
      rawEnd,
      typedPrefix,
      normalizedToken,
    };
  }

  function refreshCategorySuggestion() {
    const context = getCategoryTokenContext();
    if (!context || !context.typedPrefix) {
      clearCategorySuggestion();
      return;
    }
    const typedLower = context.typedPrefix.toLocaleLowerCase();
    const tokenLower = context.normalizedToken.toLocaleLowerCase();
    const suggestion = normalizedExistingCategories.find((candidate) => {
      const lower = candidate.toLocaleLowerCase();
      return lower.startsWith(typedLower) && lower !== tokenLower;
    });
    if (!suggestion) {
      clearCategorySuggestion();
      return;
    }
    categorySuggestion = suggestion;
    const typedRaw = context.value.slice(context.rawStart, context.caret);
    const suggestionSuffix = suggestion.slice(Math.min(typedRaw.length, suggestion.length));
    if (
      suggestionSuffix
      && context.caret === context.rawEnd
      && context.caret === context.value.length
    ) {
      categorySuggestionGhostPrefix = context.value.slice(0, context.caret);
      categorySuggestionGhostSuffix = suggestionSuffix;
      return;
    }
    categorySuggestionGhostPrefix = '';
    categorySuggestionGhostSuffix = '';
  }

  async function acceptCategorySuggestion(): Promise<boolean> {
    const context = getCategoryTokenContext();
    if (!context || !categorySuggestion) return false;
    const nextText = `${context.value.slice(0, context.rawStart)}${categorySuggestion}${context.value.slice(context.rawEnd)}`;
    if (nextText === categoryText) return false;
    categoryText = nextText;
    await tick();
    const caret = context.rawStart + categorySuggestion.length;
    categoryEl?.setSelectionRange(caret, caret);
    refreshCategorySuggestion();
    return true;
  }

  function handleCategoryFieldInput() {
    refreshCategorySuggestion();
  }

  function handleCategoryFieldCursorChange() {
    refreshCategorySuggestion();
  }

  $effect(() => {
    if (!categoryEl) return;
    normalizedExistingCategories;
    categoryText;
    refreshCategorySuggestion();
  });

  $effect(() => {
    if (app.modalOpen === 'todo') {
      tick().then(() => {
        if (todoId) modalEl?.focus();
        else summaryEl?.focus();
      });
    }
  });

  function cycleSelect(sel: HTMLSelectElement, dir: 1 | -1) {
    cycleSelectOption(sel, dir);
  }

  function parseTimezone(): string | undefined {
    return getPreferredTimezone(app.timezone);
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

  function shiftLocalDatetime(localDatetime: string, seconds: number): string {
    const shifted = new Date(new Date(localDatetime).getTime() + seconds * 1000);
    const y = shifted.getFullYear();
    const m = String(shifted.getMonth() + 1).padStart(2, '0');
    const d = String(shifted.getDate()).padStart(2, '0');
    const h = String(shifted.getHours()).padStart(2, '0');
    const min = String(shifted.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${d}T${h}:${min}`;
  }

  function clearDueFieldIfNeeded() {
    clearIfFocusOutside([dueEl, dueHumanEl], () => {
      activeDueField = false;
    });
  }

  function focusDueHumanField() {
    activateAndFocus(
      () => {
        activeDueField = true;
      },
      () => dueHumanEl,
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
      const baseDue = shiftBaseDue ?? due;
      shiftBaseDue = baseDue;
      shiftDeltaSeconds = parsed.seconds;
      shiftDeltaLabel = parsed.label;
      shiftHuman = parsed.label;
      if (baseDue) due = shiftLocalDatetime(baseDue, parsed.seconds);
      shiftLocked = true;
      activeDueField = false;
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
    if (shiftBaseDue) due = shiftBaseDue;
  }

  function onDueInput() {
    if (!shiftLocked) shiftBaseDue = null;
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
    const inTextInput = isTextInputTarget(target);

    if (
      target === categoryEl
      && e.code === 'Space'
      && (e.shiftKey || e.ctrlKey)
    ) {
      e.preventDefault();
      void acceptCategorySuggestion();
      return;
    }

    if (e.key === 'Enter' && target === categoryEl) {
      e.preventDefault();
      void acceptCategorySuggestion().then((accepted) => {
        if (accepted) return;
        if (!todoId) {
          completedEl?.focus();
          return;
        }
        blurInputAndFocusModal(categoryEl, modalEl);
      });
      return;
    }

    if (e.key === 'Enter' && target === dueHumanEl) {
      e.preventDefault();
      void applyHumanDue().then((ok) => {
        if (!ok) return;
        activeDueField = false;
        blurInputAndFocusModal(dueHumanEl, modalEl);
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
    if (target === dueEl && e.key.toLowerCase() === 'h') {
      if (shiftLocked) return;
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
    if (handleCommonModalKeydown({
      event: e,
      target,
      isTextInput: inTextInput,
      modalEl,
      onClose: onclose,
      onSubmit: submit,
      cycleSelect,
      onTextInputEscape: (activeTarget) => {
        if (activeTarget === dueHumanEl) activeDueField = false;
        if (activeTarget === repeatHumanEl) activeRepeatField = false;
        if (activeTarget === alertHumanEl) activeAlertField = false;
      },
      deleteConfirmMessage: todoId ? 'Delete this todo?' : undefined,
      onDelete: todoId ? () => { void performDelete(); } : undefined,
    })) {
      return;
    }

    if (inTextInput) return;

    const key = e.key.toLowerCase();
    if (key === 's') {
      e.preventDefault();
      summaryEl?.focus();
    } else if (key === 'a') {
      e.preventDefault();
      categoryEl?.focus();
    } else if (key === 'c') {
      e.preventDefault();
      completedEl?.focus();
    } else if (key === 'u') {
      if (shiftLocked) return;
      e.preventDefault();
      focusDueHumanField();
    } else if (key === 'f') {
      e.preventDefault();
      shiftHumanEl?.focus();
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
    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Category</span>
        <span class="field-shortcut">A</span>
      </div>
      <div class="category-input-wrap">
        <div class="category-input-shell">
          {#if categorySuggestionGhostSuffix}
            <div class="category-input-ghost" aria-hidden="true">
              <span class="category-input-ghost-prefix">{categorySuggestionGhostPrefix}</span><span class="category-input-ghost-suffix">{categorySuggestionGhostSuffix}</span>
            </div>
          {/if}
          <input
            type="text"
            class="category-input"
            bind:value={categoryText}
            bind:this={categoryEl}
            placeholder="e.g. Work, Personal"
            aria-label="Todo categories"
            aria-autocomplete="both"
            oninput={handleCategoryFieldInput}
            onfocus={refreshCategorySuggestion}
            onkeyup={handleCategoryFieldCursorChange}
            onclick={handleCategoryFieldCursorChange}
            onselect={handleCategoryFieldCursorChange}
            onblur={clearCategorySuggestion}
          />
        </div>
        {#if categorySuggestion}
          <p class="category-suggestion-note">
            Press Shift+Space or Ctrl+Space to accept.
          </p>
        {/if}
      </div>
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
        disabled={shiftLocked}
        class:opacity-60={shiftLocked}
        class:bg-[var(--bg-subtle)]={shiftLocked}
        bind:this={dueEl}
        oninput={onDueInput}
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
          disabled={shiftLocked}
          class:opacity-60={shiftLocked}
          class:bg-[var(--bg-subtle)]={shiftLocked}
          onfocus={() => { activeDueField = true; }}
          onblur={clearDueFieldIfNeeded}
        />
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
