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
    <dl class="shortcuts-list">
      <dt>1 or C</dt>
      <dd>Switch to Calendar view</dd>
      <dt>2 or T</dt>
      <dd>Switch to Todo view</dd>
      <dt>D</dt>
      <dd>Day view (calendar)</dd>
      <dt>M</dt>
      <dd>Month view (calendar)</dd>
      <dt>G or Home</dt>
      <dd>Go to today</dd>
      <dt>N</dt>
      <dd>New event (in calendar) or new todo (in todos)</dd>
      <dt>Enter</dt>
      <dd>Open selected event/todo</dd>
      <dt>J / Down</dt>
      <dd>Focus next item</dd>
      <dt>K / Up</dt>
      <dd>Focus previous item</dd>
      <dt>?</dt>
      <dd>Show this shortcuts list</dd>
      <dt>Escape</dt>
      <dd>Close modal</dd>
    </dl>
    <div class="form-actions">
      <button class="btn btn-primary" onclick={onclose} type="button">Close</button>
    </div>
  </div>
</div>

<style>
  .shortcuts-list {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.5rem 1.5rem;
    margin: 1rem 0;
  }
  .shortcuts-list dt {
    font-family: ui-monospace, monospace;
    font-weight: 600;
  }
  .shortcuts-list dd {
    margin: 0;
  }
</style>
