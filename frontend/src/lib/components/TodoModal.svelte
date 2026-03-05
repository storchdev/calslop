<script lang="ts">
  import { tick } from 'svelte';
  import { createTodo, updateTodo, getTodo, getSources, deleteTodo } from '$lib/api';
  import type { Todo, TodoCreate, TodoUpdate } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { toLocalDatetimeInput } from '$lib/date';

  interface Props {
    todoId: string | null;
    initialTodo?: Todo | null;
    onclose: () => void;
    onsave: () => void;
  }

  let { todoId, initialTodo = null, onclose, onsave }: Props = $props();

  let summary = $state('');
  let completed = $state(false);
  let due = $state('');
  let description = $state('');
  let sourceId = $state('');
  let sources = $state<{ id: string; name: string; type: string }[]>([]);
  let error = $state('');
  let saving = $state(false);

  $effect(() => {
    const tz = app.timezone || undefined;
    if (todoId) {
      if (initialTodo && initialTodo.id === todoId) {
        summary = initialTodo.summary;
        completed = initialTodo.completed;
        due = initialTodo.due ? toLocalDatetimeInput(initialTodo.due, tz) : '';
        description = initialTodo.description ?? '';
        return;
      }
      getTodo(todoId).then((t) => {
        summary = t.summary;
        completed = t.completed;
        due = t.due ? toLocalDatetimeInput(t.due, tz) : '';
        description = t.description ?? '';
      });
    }
  });

  $effect(() => {
    getSources().then((s) => {
      sources = s.filter((x) => x.type === 'local_folder' || x.type === 'caldav').map((x) => ({ id: x.id, name: x.name, type: x.type }));
      if (sources.length && !todoId) sourceId = sources[0].id;
    });
  });

  async function submit() {
    error = '';
    if (!summary.trim()) {
      error = 'Summary is required';
      return;
    }
    saving = true;
    try {
      if (todoId) {
        await updateTodo(todoId, { summary: summary.trim(), completed, due: due ? new Date(due).toISOString() : null, description: description || null });
      } else {
        if (!sourceId) {
          error = 'Select a todo source';
          return;
        }
        await createTodo({ source_id: sourceId, summary: summary.trim(), completed, due: due ? new Date(due).toISOString() : null, description: description || null });
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
  let summaryEl: HTMLInputElement | undefined;
  let completedEl: HTMLInputElement | undefined;
  let dueEl: HTMLInputElement | undefined;
  let descriptionEl: HTMLTextAreaElement | undefined;
  let sourceIdEl: HTMLSelectElement | undefined;

  $effect(() => {
    if (app.modalOpen === 'todo') {
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
    if (todoId && e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'd') {
      e.preventDefault();
      if (confirm('Delete this todo?')) {
        deleteTodo(todoId).then(() => {
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
    if (key === 's') {
      e.preventDefault();
      summaryEl?.focus();
    } else if (key === 'c') {
      e.preventDefault();
      completedEl?.focus();
    } else if (key === 'u') {
      e.preventDefault();
      dueEl?.focus();
    } else if (key === 'd') {
      e.preventDefault();
      descriptionEl?.focus();
    } else if (key === 'l' && sourceIdEl) {
      e.preventDefault();
      sourceIdEl.focus();
    }
  }
</script>

<div class="modal-backdrop" role="dialog" aria-modal="true" onkeydown={handleKeydown} onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="modal" tabindex="-1" bind:this={modalEl} onclick={(e) => e.stopPropagation()}>
    <h2>{todoId ? 'Edit todo' : 'New todo'}</h2>
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
      <input type="datetime-local" bind:value={due} bind:this={dueEl} />
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
      {#if todoId}
        <div class="form-action-with-hint">
          <button
            class="btn btn-ghost"
            type="button"
            disabled={saving}
            onclick={async () => {
              if (!confirm('Delete this todo?')) return;
              try {
                await deleteTodo(todoId);
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
