<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { app } from '$lib/stores/app.svelte';
  import { parseHumanDatetime } from '$lib/api';
  import { toLocalDatetimeInput } from '$lib/date';
  import { getPreferredTimezone, localNowInput } from '$lib/modal-utils';
  import { isTextInputTarget } from '$lib/modal-keyboard';
  import { clearIfFocusOutside } from '$lib/modal-focus';

  interface Props {
    onclose: () => void;
    onapply: (startIso: string | null, endIso: string | null, days: number, overdueOnly: boolean) => Promise<void> | void;
  }

  let { onclose, onapply }: Props = $props();

  let modalEl: HTMLDivElement | undefined;
  let startEl: HTMLInputElement | undefined;
  let endEl: HTMLInputElement | undefined;
  let daysEl: HTMLInputElement | undefined;
  let startHumanEl = $state<HTMLInputElement | undefined>(undefined);
  let endHumanEl = $state<HTMLInputElement | undefined>(undefined);

  let startLocal = $state('');
  let endLocal = $state('');
  let days = $state('1');

  let startHuman = $state('');
  let endHuman = $state('');
  let activeStartHuman = $state(false);
  let activeEndHuman = $state(false);

  let submitting = $state(false);
  let error = $state('');
  let overdueOnly = $state(false);

  onMount(() => {
    tick().then(() => modalEl?.focus());
  });

  function parseTimezone(): string | undefined {
    return getPreferredTimezone(app.timezone, false);
  }

  async function applyHumanStart(): Promise<boolean> {
    const text = startHuman.trim();
    if (!text) return false;
    error = '';
    try {
      const parsed = await parseHumanDatetime(text, parseTimezone(), startLocal || localNowInput());
      startLocal = toLocalDatetimeInput(parsed.iso, app.timezone || undefined);
      return true;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to parse start date/time';
      return false;
    }
  }

  async function applyHumanEnd(): Promise<boolean> {
    const text = endHuman.trim();
    if (!text) return false;
    error = '';
    try {
      const context = endLocal || startLocal || localNowInput();
      const parsed = await parseHumanDatetime(text, parseTimezone(), context);
      endLocal = toLocalDatetimeInput(parsed.iso, app.timezone || undefined);
      return true;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to parse end date/time';
      return false;
    }
  }

  function clearStartHumanIfNeeded() {
    clearIfFocusOutside([startEl, startHumanEl], () => {
      activeStartHuman = false;
    });
  }

  function clearEndHumanIfNeeded() {
    clearIfFocusOutside([endEl, endHumanEl], () => {
      activeEndHuman = false;
    });
  }

  async function submit() {
    if (submitting) return;
    error = '';
    if (!overdueOnly && (!startLocal || !endLocal)) {
      error = 'Please provide both start and end date/time.';
      return;
    }
    const n = Number(days);
    if (!Number.isInteger(n)) {
      error = 'Days must be an integer.';
      return;
    }

    submitting = true;
    try {
      let startIso: string | null = null;
      let endIso: string | null = null;
      if (!overdueOnly) {
        const startDate = new Date(startLocal);
        const endDate = new Date(endLocal);
        if (!Number.isFinite(startDate.getTime()) || !Number.isFinite(endDate.getTime())) {
          throw new Error('Please provide valid start and end date/time.');
        }
        if (endDate.getTime() < startDate.getTime()) {
          throw new Error('End must be on or after start.');
        }
        startIso = startDate.toISOString();
        endIso = endDate.toISOString();
      }
      await onapply(startIso, endIso, n, overdueOnly);
      onclose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to push todos';
    } finally {
      submitting = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement | null;
    if (!target) return;
    const inTextInput = isTextInputTarget(target);

    if (e.key === 'Escape') {
      if (inTextInput) {
        e.preventDefault();
        if (target === startHumanEl) activeStartHuman = false;
        if (target === endHumanEl) activeEndHuman = false;
        target.blur();
        modalEl?.focus();
      } else {
        onclose();
      }
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      void submit();
      return;
    }
    if (target === startEl && e.key.toLowerCase() === 'h') {
      e.preventDefault();
      activeStartHuman = true;
      tick().then(() => startHumanEl?.focus());
      return;
    }
    if (target === endEl && e.key.toLowerCase() === 'h') {
      e.preventDefault();
      activeEndHuman = true;
      tick().then(() => endHumanEl?.focus());
      return;
    }
    if (e.key === 'Enter' && target === startHumanEl) {
      e.preventDefault();
      void applyHumanStart().then((ok) => {
        if (!ok) return;
        activeStartHuman = false;
        activeEndHuman = true;
        tick().then(() => endHumanEl?.focus());
      });
      return;
    }
    if (e.key === 'Enter' && target === endHumanEl) {
      e.preventDefault();
      void applyHumanEnd().then((ok) => {
        if (!ok) return;
        activeEndHuman = false;
        daysEl?.focus();
        daysEl?.select();
      });
      return;
    }

    if (!inTextInput && !e.shiftKey && (e.key === 'j' || e.key === 'k')) {
      e.preventDefault();
      if (modalEl) modalEl.scrollTop += e.key === 'j' ? 60 : -60;
      return;
    }

    if (inTextInput) return;

    if (!e.ctrlKey && !e.metaKey && !e.altKey) {
      const k = e.key.toLowerCase();
      if (k === 's') {
        e.preventDefault();
        startEl?.focus();
        return;
      }
      if (k === 'e') {
        e.preventDefault();
        endEl?.focus();
        return;
      }
      if (k === 'd') {
        e.preventDefault();
        daysEl?.focus();
        daysEl?.select();
        return;
      }
      if (k === 'o') {
        e.preventDefault();
        overdueOnly = !overdueOnly;
        if (overdueOnly) {
          activeStartHuman = false;
          activeEndHuman = false;
          modalEl?.focus();
        }
      }
    }
  }
</script>

<div class="modal-backdrop" role="dialog" aria-modal="true" onkeydown={handleKeydown} onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="modal" tabindex="-1" bind:this={modalEl} onclick={(e) => e.stopPropagation()}>
    <h2>Push off todos</h2>
    {#if error}
      <p class="text-red-600 text-sm">{error}</p>
    {/if}

    <form onsubmit={(e) => { e.preventDefault(); void submit(); }}>
    {#if submitting}
      <p class="modal-loading flex items-center gap-2 text-[var(--text-muted)]" aria-busy="true" aria-live="polite">
        <span class="todo-loading-spinner" aria-hidden="true"></span>
        Updating…
      </p>
    {/if}

    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">Push todos due between</span>
        <span class="key-hint">S</span>
      </div>
      <input
        type="datetime-local"
        bind:value={startLocal}
        bind:this={startEl}
        disabled={overdueOnly}
        class:opacity-60={overdueOnly}
        onfocus={() => { if (!overdueOnly) activeStartHuman = true; }}
        onblur={clearStartHumanIfNeeded}
      />
    </div>
    {#if activeStartHuman && !overdueOnly}
      <div class="form-row">
        <div class="form-row-header">
          <span class="field-label">Human-friendly</span>
          <span class="key-hint">H</span>
        </div>
        <input
          type="text"
          bind:value={startHuman}
          bind:this={startHumanEl}
          placeholder="e.g. today 4pm"
          onfocus={() => { activeStartHuman = true; }}
          onblur={clearStartHumanIfNeeded}
        />
      </div>
    {/if}

    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">and</span>
        <span class="key-hint">E</span>
      </div>
      <input
        type="datetime-local"
        bind:value={endLocal}
        bind:this={endEl}
        disabled={overdueOnly}
        class:opacity-60={overdueOnly}
        onfocus={() => { if (!overdueOnly) activeEndHuman = true; }}
        onblur={clearEndHumanIfNeeded}
      />
    </div>
    {#if activeEndHuman && !overdueOnly}
      <div class="form-row">
        <div class="form-row-header">
          <span class="field-label">Human-friendly</span>
          <span class="key-hint">H</span>
        </div>
        <input
          type="text"
          bind:value={endHuman}
          bind:this={endHumanEl}
          placeholder="e.g. tomorrow 8am"
          onfocus={() => { activeEndHuman = true; }}
          onblur={clearEndHumanIfNeeded}
        />
      </div>
    {/if}

    <div class="font-bold text-sm">OR</div>

    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">everything overdue</span>
      </div>
      <div class="inline-flex items-center gap-2">
        <input type="checkbox" bind:checked={overdueOnly} />
        <span class="key-hint">O</span>
      </div>
    </div>

    <hr class="border-[var(--border)] my-1" />

    <div class="form-row">
      <div class="form-row-header">
        <span class="field-label">forward by</span>
        <span class="key-hint">D</span>
      </div>
      <div class="flex flex-col items-stretch gap-1">
        <input type="number" step="1" bind:value={days} bind:this={daysEl} class="w-full" />
        <span class="text-[var(--text-muted)] text-sm">days</span>
      </div>
    </div>

    <div class="form-actions">
      <div class="form-action-with-hint">
        <button class="btn btn-primary" type="submit" disabled={submitting}>Apply</button>
        <span class="action-hint">Ctrl+Enter</span>
      </div>
      <div class="form-action-with-hint">
        <button class="btn btn-ghost" type="button" onclick={onclose} disabled={submitting}>Cancel</button>
        <span class="action-hint">Esc</span>
      </div>
    </div>
    </form>
  </div>
</div>
