<script lang="ts">
  interface Props {
    onclose: () => void;
  }

  let { onclose }: Props = $props();
  let modalEl: HTMLDivElement | undefined;

  $effect(() => {
    if (!modalEl) return;
    const fn = (e: KeyboardEvent) => {
      if (!e.shiftKey && (e.key === 'j' || e.key === 'k')) {
        e.preventDefault();
        e.stopPropagation();
        modalEl!.scrollTop += e.key === 'j' ? 60 : -60;
      }
    };
    window.addEventListener('keydown', fn, true);
    return () => window.removeEventListener('keydown', fn, true);
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }
</script>

<div class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" onkeydown={handleKeydown} onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="modal shortcuts-modal" tabindex="-1" bind:this={modalEl} onclick={(e) => e.stopPropagation()}>
    <h2>Keyboard shortcuts</h2>
    <dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 my-4">
      <dt class="font-mono font-semibold">1 or C</dt>
      <dd class="m-0">Switch to Calendar view</dd>
      <dt class="font-mono font-semibold">2 or T</dt>
      <dd class="m-0">Switch to Todo view</dd>
      <dt class="font-mono font-semibold">D</dt>
      <dd class="m-0">Day view (calendar)</dd>
      <dt class="font-mono font-semibold">M</dt>
      <dd class="m-0">Month view (calendar)</dd>
      <dt class="font-mono font-semibold">G or Home</dt>
      <dd class="m-0">Go to today</dd>
      <dt class="font-mono font-semibold">N</dt>
      <dd class="m-0">New event (in calendar) or new todo (in todos)</dd>
      <dt class="font-mono font-semibold">Enter</dt>
      <dd class="m-0">Open selected event/todo; in month view open day view for focused day</dd>
      <dt class="font-mono font-semibold">H / Left</dt>
      <dd class="m-0">Previous day (calendar)</dd>
      <dt class="font-mono font-semibold">L / Right</dt>
      <dd class="m-0">Next day (calendar)</dd>
      <dt class="font-mono font-semibold">J / Down</dt>
      <dd class="m-0">Month: next week. Day view: next event/todo (jump). Todos: focus next</dd>
      <dt class="font-mono font-semibold">K / Up</dt>
      <dd class="m-0">Month: previous week. Day view: previous event/todo (jump). Todos: focus prev</dd>
      <dt class="font-mono font-semibold">j / k</dt>
      <dd class="m-0">Day view: scroll timeline down / up</dd>
      <dt class="font-mono font-semibold">X or Space</dt>
      <dd class="m-0">Todos / Day view: toggle focused todo completed</dd>
      <dt class="font-mono font-semibold">S</dt>
      <dd class="m-0">Todo view: toggle show/hide completed todos</dd>
      <dt class="font-mono font-semibold">Shift+H/J/K/L</dt>
      <dd class="m-0">Month view: change month. Day view: change week</dd>
      <dt class="font-mono font-semibold">V</dt>
      <dd class="m-0">Cycle calendar density (minimal → balanced → dense)</dd>
      <dt class="font-mono font-semibold">Y</dt>
      <dd class="m-0">Toggle show todos on calendar</dd>
      <dt class="font-mono font-semibold">R</dt>
      <dd class="m-0">Sync calendars and todos</dd>
      <dt class="font-mono font-semibold">/</dt>
      <dd class="m-0">Focus search bar (month view / todo view)</dd>
      <dt class="font-mono font-semibold">Enter (in search)</dt>
      <dd class="m-0">Apply filter and exit to calendar/todos (search mode); then navigate with j/k or arrows</dd>
      <dt class="font-mono font-semibold">Escape (search mode)</dt>
      <dd class="m-0">Exit search mode and clear search bar</dd>
      <dt class="font-mono font-semibold">B</dt>
      <dd class="m-0">Hide/show navbar</dd>
      <dt class="font-mono font-semibold">?</dt>
      <dd class="m-0">Show this shortcuts list</dd>
      <dt class="font-mono font-semibold">Escape</dt>
      <dd class="m-0">Close modal</dd>
      <dt class="font-mono font-semibold">j / k</dt>
      <dd class="m-0">Modals: scroll content</dd>
      <dt class="font-mono font-semibold">Event/todo modals</dt>
      <dd class="m-0">Ctrl+Enter save, Ctrl+Shift+D delete (when editing), Esc cancel. Single key (T, S, …) jumps to field. In date inputs, H opens Human-friendly parse; Enter applies; Esc exits. Shift+J / Shift+K cycle dropdown options.</dd>
    </dl>
    <div class="form-actions">
      <button class="btn btn-primary" onclick={onclose} type="button">Close</button>
    </div>
  </div>
</div>
