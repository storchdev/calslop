<script lang="ts">
  interface Props {
    onclose: () => void;
  }

  let { onclose }: Props = $props();

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }
</script>

<div class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" onkeydown={handleKeydown} onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="modal shortcuts-modal" onclick={(e) => e.stopPropagation()}>
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
      <dd class="m-0">Open selected event/todo</dd>
      <dt class="font-mono font-semibold">H / Left</dt>
      <dd class="m-0">Previous day (calendar)</dd>
      <dt class="font-mono font-semibold">L / Right</dt>
      <dd class="m-0">Next day (calendar)</dd>
      <dt class="font-mono font-semibold">J / Down</dt>
      <dd class="m-0">Next day / focus next item</dd>
      <dt class="font-mono font-semibold">K / Up</dt>
      <dd class="m-0">Previous day / focus previous item</dd>
      <dt class="font-mono font-semibold">?</dt>
      <dd class="m-0">Show this shortcuts list</dd>
      <dt class="font-mono font-semibold">Escape</dt>
      <dd class="m-0">Close modal</dd>
    </dl>
    <div class="form-actions">
      <button class="btn btn-primary" onclick={onclose} type="button">Close</button>
    </div>
  </div>
</div>
