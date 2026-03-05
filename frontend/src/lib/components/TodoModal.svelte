<script lang="ts">
  import { createTodo, updateTodo, getTodo, getSources, deleteTodo } from '$lib/api';
  import type { Todo, TodoCreate, TodoUpdate } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';

  interface Props {
    todoId: string | null;
    onclose: () => void;
    onsave: () => void;
  }

  let { todoId, onclose, onsave }: Props = $props();

  let summary = $state('');
  let completed = $state(false);
  let due = $state('');
  let description = $state('');
  let sourceId = $state('');
  let sources = $state<{ id: string; name: string; type: string }[]>([]);
  let error = $state('');
  let saving = $state(false);

  $effect(() => {
    if (todoId) {
      getTodo(todoId).then((t) => {
        summary = t.summary;
        completed = t.completed;
        due = t.due ? t.due.slice(0, 10) : '';
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
        await updateTodo(todoId, { summary: summary.trim(), completed, due: due || null, description: description || null });
      } else {
        if (!sourceId) {
          error = 'Select a todo source';
          return;
        }
        await createTodo({ source_id: sourceId, summary: summary.trim(), completed, due: due || null, description: description || null });
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
    <h2>{todoId ? 'Edit todo' : 'New todo'}</h2>
    {#if error}
      <p class="text-red-600 text-sm">{error}</p>
    {/if}
    {#if !todoId}
      <div class="form-row">
        <label>List</label>
        <select bind:value={sourceId}>
          {#each sources as s}
            <option value={s.id}>{s.name}</option>
          {/each}
        </select>
      </div>
    {/if}
    <div class="form-row">
      <label>Summary</label>
      <input type="text" bind:value={summary} />
    </div>
    <div class="form-row">
      <label><input type="checkbox" bind:checked={completed} /> Completed</label>
    </div>
    <div class="form-row">
      <label>Due date</label>
      <input type="date" bind:value={due} />
    </div>
    <div class="form-row">
      <label>Description</label>
      <textarea bind:value={description} rows="3"></textarea>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick={submit} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
      {#if todoId}
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
      {/if}
      <button class="btn btn-ghost" onclick={onclose} type="button">Cancel</button>
    </div>
  </div>
</div>
