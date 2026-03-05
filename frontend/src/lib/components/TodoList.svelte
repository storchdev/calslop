<script lang="ts">
  import type { Todo } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { formatInTimezone } from '$lib/date';

  interface Props {
    todos: Todo[];
    onToggle?: (todo: Todo) => void;
    onSelect?: (todo: Todo) => void;
  }

  let { todos, onToggle, onSelect }: Props = $props();
</script>

<div id="todo-view" class="p-4" role="list">
  {#each todos as todo, i}
    <div
      role="listitem"
      class="todo-item flex items-center gap-2"
      class:completed={todo.completed}
      class:focused={app.focusedTodoIndex === i}
      tabindex={app.focusedTodoIndex === i ? 0 : -1}
      onclick={() => onSelect?.(todo)}
      onkeydown={(e) => {
        if (e.key === 'Enter') onSelect?.(todo);
        if (e.key === 'j' || e.key === 'ArrowDown') {
          e.preventDefault();
          if (i < todos.length - 1) {
            app.setFocusedTodoIndex(i + 1);
            (e.currentTarget.nextElementSibling as HTMLElement)?.focus();
          }
        }
        if (e.key === 'k' || e.key === 'ArrowUp') {
          e.preventDefault();
          if (i > 0) {
            app.setFocusedTodoIndex(i - 1);
            (e.currentTarget.previousElementSibling as HTMLElement)?.focus();
          }
        }
      }}
    >
      <input
        type="checkbox"
        checked={todo.completed}
        onchange={() => onToggle?.(todo)}
        onclick={(e) => e.stopPropagation()}
        aria-label="Toggle completed"
      />
      <span class="flex-1">{todo.summary}</span>
      {#if todo.recurrence}
        <span class="text-[var(--text-muted)]" title="Repeating" aria-hidden="true">↻</span>
      {/if}
      {#if todo.due}
        <span class="text-sm text-[var(--text-muted)]">{formatInTimezone(todo.due, { dateStyle: 'short', timeStyle: 'short' }, app.timezone || undefined)}</span>
      {/if}
    </div>
  {/each}
  {#if todos.length === 0}
    <p class="text-[var(--text-muted)]">No todos.</p>
  {/if}
</div>
