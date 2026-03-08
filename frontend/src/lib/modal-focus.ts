import { tick } from 'svelte';

export function activateAndFocus(
  activate: () => void,
  target: () => HTMLElement | undefined,
): void {
  activate();
  void tick().then(() => target()?.focus());
}

export function clearIfFocusOutside(
  elements: Array<HTMLElement | undefined>,
  clear: () => void,
): void {
  void tick().then(() => {
    const active = document.activeElement;
    const stillInside = elements.some((element) => element === active);
    if (!stillInside) clear();
  });
}

export function blurInputAndFocusModal(
  input: HTMLElement | undefined,
  modal: HTMLDivElement | undefined,
): void {
  input?.blur();
  modal?.focus();
}
