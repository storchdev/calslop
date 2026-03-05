<script lang="ts">
  import type { Todo } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';

  interface Props {
    todos: Todo[];
    onToggle?: (todo: Todo) => void;
    onSelect?: (todo: Todo) => void;
  }

  let { todos, onToggle, onSelect }: Props = $props();
</script>

<div id="todo-view" class="todo-list" role="list">
  {#each todos as todo, i}
    <div
      role="listitem"
      class="todo-item"
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
      <span class="todo-summary">{todo.summary}</span>
      {#if todo.due}
        <span class="todo-due">{new Date(todo.due).toLocaleDateString()}</span>
      {/if}
    </div>
  {/each}
  {#if todos.length === 0}
    <p class="text-muted">No todos.</p>
  {/if}
</div>

<style>
  .todo-list {
    padding: 1rem;
  }
  .todo-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    cursor: pointer;
    border: 1px solid transparent;
  }
  .todo-item:hover,
  .todo-item:focus {
    background: var(--bg-elevated);
  }
  .todo-item.focused {
    box-shadow: 0 0 0 2px var(--accent);
  }
  .todo-summary {
    flex: 1;
  }
  .todo-due {
    font-size: 0.875rem;
    color: var(--text-muted);
  }
  .text-muted {
    color: var(--text-muted);
  }
</style>
