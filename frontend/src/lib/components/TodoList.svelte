<script lang="ts">
  import type { Todo } from '$lib/types';
  import { app } from '$lib/stores/app.svelte';
  import { formatInTimezone, parseUtcIfNeeded } from '$lib/date';

  const UNCATEGORIZED_KEY = '__uncategorized__';
  const UNCATEGORIZED_LABEL = 'Uncategorized';

  type TodoCategoryGroup = {
    key: string;
    label: string;
    todos: Todo[];
  };

  interface Props {
    todos: Todo[];
    showCompleted?: boolean;
    todoOrder?: 'oldest' | 'newest';
    searchQuery?: string;
    /** When set, the todo with this id is shown as a loading row instead of normal content. */
    loadingTodoId?: string | null;
    onToggle?: (todo: Todo) => void;
    onSelect?: (todo: Todo) => void;
    /** When false, only render the list (toolbar is rendered by parent). */
    showToolbar?: boolean;
  }

  let { todos, showCompleted = false, todoOrder = 'oldest', searchQuery = '', loadingTodoId = null, onToggle, onSelect, showToolbar = true }: Props = $props();

  function matchesSearch(todo: Todo, q: string): boolean {
    if (!q.trim()) return true;
    const lower = q.toLowerCase();
    return (
      todo.summary.toLowerCase().includes(lower) ||
      (todo.description?.toLowerCase().includes(lower) ?? false)
    );
  }

  function isTodoOverdue(todo: Todo): boolean {
    if (todo.completed || !todo.due) return false;
    return parseUtcIfNeeded(todo.due).getTime() < Date.now();
  }

  function primaryCategory(todo: Todo): { key: string; label: string } {
    const first = (todo.categories ?? []).find((category) => category.trim().length > 0)?.trim();
    if (!first) {
      return { key: UNCATEGORIZED_KEY, label: UNCATEGORIZED_LABEL };
    }
    return { key: `category:${first.toLocaleLowerCase()}`, label: first };
  }

  const filtered = $derived(
    showCompleted ? todos : todos.filter((t) => !t.completed || t.id === loadingTodoId)
  );
  const searchFiltered = $derived(
    searchQuery.trim() ? filtered.filter((t) => matchesSearch(t, searchQuery)) : filtered
  );
  const sortedTodos = $derived(
    [...searchFiltered].sort((a, b) => {
      const aDue = a.due ? parseUtcIfNeeded(a.due).getTime() : null;
      const bDue = b.due ? parseUtcIfNeeded(b.due).getTime() : null;
      if (aDue === null && bDue === null) return 0;
      if (aDue === null) return todoOrder === 'oldest' ? 1 : -1;
      if (bDue === null) return todoOrder === 'oldest' ? -1 : 1;
      return todoOrder === 'oldest' ? aDue - bDue : bDue - aDue;
    })
  );
  const groupedTodos = $derived.by(() => {
    const map = new Map<string, TodoCategoryGroup>();
    for (const todo of sortedTodos) {
      const { key, label } = primaryCategory(todo);
      let group = map.get(key);
      if (!group) {
        group = { key, label, todos: [] };
        map.set(key, group);
      }
      group.todos.push(todo);
    }
    const groups = [...map.values()];
    groups.sort((a, b) => {
      if (a.key === UNCATEGORIZED_KEY) return 1;
      if (b.key === UNCATEGORIZED_KEY) return -1;
      return a.label.localeCompare(b.label, undefined, { sensitivity: 'base' });
    });
    return groups;
  });
  let collapsedCategoryKeys = $state(new Set<string>());
  const visibleTodoRows = $derived.by(() => {
    const rows: Todo[] = [];
    for (const group of groupedTodos) {
      if (!collapsedCategoryKeys.has(group.key)) rows.push(...group.todos);
    }
    return rows;
  });
  const visibleTodoIndexById = $derived.by(() => {
    const indexById = new Map<string, number>();
    visibleTodoRows.forEach((todo, index) => {
      indexById.set(todo.id, index);
    });
    return indexById;
  });
  const completedCount = $derived(todos.filter((t) => t.completed).length);
  const timeDisplayFormat = $derived(app.timeDisplayFormat);
  let focusedCategoryKey = $state<string | null>(null);

  function toggleCategory(groupKey: string): void {
    const next = new Set(collapsedCategoryKeys);
    if (next.has(groupKey)) next.delete(groupKey);
    else next.add(groupKey);
    collapsedCategoryKeys = next;
  }

  $effect(() => {
    const valid = new Set(groupedTodos.map((group) => group.key));
    const next = new Set([...collapsedCategoryKeys].filter((groupKey) => valid.has(groupKey)));
    if (next.size !== collapsedCategoryKeys.size) {
      collapsedCategoryKeys = next;
    }
  });

  // Keep focused index in range when visible list changes
  $effect(() => {
    if (visibleTodoRows.length === 0) {
      app.setFocusedTodoIndex(-1);
      return;
    }
    if (focusedCategoryKey !== null) {
      if (app.focusedTodoIndex !== -1) app.setFocusedTodoIndex(-1);
      return;
    }
    if (app.focusedTodoIndex < 0 || app.focusedTodoIndex >= visibleTodoRows.length) {
      app.setFocusedTodoIndex(0);
    }
  });
</script>

<div id="todo-view" class="p-4 pb-14">
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
    </div>
  {/if}
  {#each groupedTodos as group, categoryIndex (group.key)}
    {@const collapsed = collapsedCategoryKeys.has(group.key)}
    {@const firstTodoIndex = !collapsed && group.todos.length > 0 ? (visibleTodoIndexById.get(group.todos[0].id) ?? -1) : -1}
    <section class="todo-category-section" class:is-focused={focusedCategoryKey === group.key}>
      <button
        type="button"
        class="todo-category-header"
        data-todo-category-index={categoryIndex}
        data-todo-category-key={group.key}
        data-todo-category-first-index={firstTodoIndex}
        aria-expanded={!collapsed}
        onclick={() => toggleCategory(group.key)}
        onfocus={() => {
          focusedCategoryKey = group.key;
          app.setFocusedTodoIndex(-1);
        }}
        onblur={() => {
          focusedCategoryKey = null;
        }}
      >
        <span class="todo-category-caret" aria-hidden="true">{collapsed ? '▸' : '▾'}</span>
        <span class="todo-category-title">{group.label}</span>
        <span class="todo-category-count">({group.todos.length})</span>
      </button>
      {#if !collapsed}
        {#each group.todos as todo (todo.id)}
          {@const i = visibleTodoIndexById.get(todo.id) ?? -1}
          <div
            role="listitem"
            class="todo-item flex items-center gap-2"
            class:completed={todo.completed && loadingTodoId !== todo.id}
            class:focused={focusedCategoryKey === null && app.focusedTodoIndex === i && loadingTodoId !== todo.id}
            class:overdue={isTodoOverdue(todo) && loadingTodoId !== todo.id}
            tabindex={app.focusedTodoIndex === i ? 0 : -1}
            data-todo-item-index={i}
            onclick={() => loadingTodoId !== todo.id && onSelect?.(todo)}
            onkeydown={(e) => {
              if (loadingTodoId === todo.id) return;
              if (e.key === 'Enter') onSelect?.(todo);
              if (e.key === ' ' || e.key === 'x' || e.key === 'X') {
                e.preventDefault();
                onToggle?.(todo);
              }
              if (e.key === 'j' || e.key === 'ArrowDown') {
                e.preventDefault();
                if (i < visibleTodoRows.length - 1) {
                  const next = i + 1;
                  app.setFocusedTodoIndex(next);
                  (document.querySelector(`[data-todo-item-index="${next}"]`) as HTMLElement | null)?.focus();
                }
              }
              if (e.key === 'k' || e.key === 'ArrowUp') {
                e.preventDefault();
                if (i > 0) {
                  const prev = i - 1;
                  app.setFocusedTodoIndex(prev);
                  (document.querySelector(`[data-todo-item-index="${prev}"]`) as HTMLElement | null)?.focus();
                }
              }
            }}
          >
            {#if loadingTodoId === todo.id}
              <span class="flex-1 flex items-center gap-2 text-[var(--text-muted)]" aria-busy="true" aria-live="polite">
                <span class="todo-loading-spinner" aria-hidden="true"></span>
                Updating…
              </span>
            {:else}
              <input
                type="checkbox"
                checked={todo.completed}
                onchange={() => onToggle?.(todo)}
                onclick={(e) => e.stopPropagation()}
                aria-label="Toggle completed"
              />
              <span class="flex-1 todo-summary">{todo.summary}</span>
              {#if todo.recurrence}
                <span class="text-[var(--text-muted)]" title="Repeating" aria-hidden="true">↻</span>
              {/if}
              {#if todo.due}
                <span class="text-sm text-[var(--text-muted)] todo-due">{formatInTimezone(todo.due, { dateStyle: 'short', timeStyle: 'short' }, app.timezone || undefined, timeDisplayFormat)}</span>
              {/if}
            {/if}
          </div>
        {/each}
      {/if}
    </section>
  {/each}
  {#if groupedTodos.length === 0}
    <p class="text-[var(--text-muted)]">No todos.</p>
  {:else if visibleTodoRows.length === 0}
    <p class="text-[var(--text-muted)]">All categories are collapsed.</p>
  {/if}
  <div class="fixed bottom-0 left-0 right-0 z-40 border-t border-[var(--border)] bg-[var(--bg)] px-4 py-2">
    <p class="text-xs text-[var(--text-muted)]" title="Total and completed count in current data">
      ({todos.length} total, {completedCount} completed)
    </p>
  </div>
</div>
