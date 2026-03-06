<script lang="ts">
  import type { Todo } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { formatInTimezone } from '$lib/date';

  interface Props {
    todos: Todo[];
    showCompleted?: boolean;
    todoOrder?: 'oldest' | 'newest';
    onToggle?: (todo: Todo) => void;
    onSelect?: (todo: Todo) => void;
    /** When false, only render the list (toolbar is rendered by parent). */
    showToolbar?: boolean;
  }

  let { todos, showCompleted = false, todoOrder = 'oldest', onToggle, onSelect, showToolbar = true }: Props = $props();

  const filtered = $derived(showCompleted ? todos : todos.filter((t) => !t.completed));
  const visibleTodos = $derived(
    [...filtered].sort((a, b) => {
      const aDue = a.due ? new Date(a.due).getTime() : null;
      const bDue = b.due ? new Date(b.due).getTime() : null;
      if (aDue === null && bDue === null) return 0;
      if (aDue === null) return todoOrder === 'oldest' ? 1 : -1;
      if (bDue === null) return todoOrder === 'oldest' ? -1 : 1;
      return todoOrder === 'oldest' ? aDue - bDue : bDue - aDue;
    })
  );
  const completedCount = $derived(todos.filter((t) => t.completed).length);

  // Keep focused index in range when visible list changes
  $effect(() => {
    if (visibleTodos.length === 0) {
      app.setFocusedTodoIndex(-1);
      return;
    }
    if (app.focusedTodoIndex < 0 || app.focusedTodoIndex >= visibleTodos.length) {
      app.setFocusedTodoIndex(0);
    }
  });
</script>

<div id="todo-view" class="p-4" role="list">
  {#if showToolbar}
    <div class="flex flex-wrap items-center gap-4 mb-3">
      <button
        type="button"
        class="btn btn-ghost text-sm inline-flex items-baseline gap-1.5"
        onclick={() => app.toggleShowCompletedTodos()}
        title="Toggle show completed todos (S)"
      >
        {showCompleted ? 'Hide completed' : 'Show completed'}
        <span class="key-hint">S</span>
      </button>
      <div class="dropdown-box">
        <span class="dropdown-box-label">Order</span>
        <select
          value={todoOrder}
          onchange={(e) => app.setTodoOrder((e.currentTarget as HTMLSelectElement).value as 'oldest' | 'newest')}
        >
          <option value="oldest">Oldest first</option>
          <option value="newest">Newest first</option>
        </select>
      </div>
      <span class="text-xs text-[var(--text-muted)]" title="Total and completed count in current data">
        ({todos.length} total, {completedCount} completed)
      </span>
    </div>
  {/if}
  {#each visibleTodos as todo, i (todo.id)}
    <div
      role="listitem"
      class="todo-item flex items-center gap-2"
      class:completed={todo.completed}
      class:focused={app.focusedTodoIndex === i}
      tabindex={app.focusedTodoIndex === i ? 0 : -1}
      data-todo-item-index={i}
      onclick={() => onSelect?.(todo)}
      onkeydown={(e) => {
        if (e.key === 'Enter') onSelect?.(todo);
        if (e.key === ' ' || e.key === 'x' || e.key === 'X') {
          e.preventDefault();
          onToggle?.(todo);
        }
        if (e.key === 'j' || e.key === 'ArrowDown') {
          e.preventDefault();
          if (i < visibleTodos.length - 1) {
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
  {#if visibleTodos.length === 0}
    <p class="text-[var(--text-muted)]">No todos.</p>
  {/if}
</div>
