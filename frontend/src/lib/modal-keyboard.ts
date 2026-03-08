export function isTextInputTarget(target: HTMLElement): boolean {
  return (
    (target instanceof HTMLInputElement && target.type !== 'checkbox' && target.type !== 'radio') ||
    target instanceof HTMLTextAreaElement
  );
}

interface CommonModalKeydownOptions {
  event: KeyboardEvent;
  target: HTMLElement;
  isTextInput: boolean;
  modalEl?: HTMLDivElement;
  onClose: () => void;
  onSubmit: () => void;
  cycleSelect: (sel: HTMLSelectElement, dir: 1 | -1) => void;
  onTextInputEscape: (target: HTMLElement) => void;
  deleteConfirmMessage?: string;
  onDelete?: () => void;
}

export function handleCommonModalKeydown(options: CommonModalKeydownOptions): boolean {
  const {
    event,
    target,
    isTextInput,
    modalEl,
    onClose,
    onSubmit,
    cycleSelect,
    onTextInputEscape,
    deleteConfirmMessage,
    onDelete,
  } = options;

  if (event.key === 'Escape') {
    if (isTextInput) {
      event.preventDefault();
      onTextInputEscape(target);
      target.blur();
      modalEl?.focus();
    } else {
      onClose();
    }
    return true;
  }

  if (event.ctrlKey && event.key === 'Enter') {
    event.preventDefault();
    onSubmit();
    return true;
  }

  if (onDelete && deleteConfirmMessage && event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'd') {
    event.preventDefault();
    if (confirm(deleteConfirmMessage)) onDelete();
    return true;
  }

  if (target instanceof HTMLSelectElement) {
    if (event.shiftKey && event.key.toLowerCase() === 'j') {
      event.preventDefault();
      cycleSelect(target, 1);
      return true;
    }
    if (event.shiftKey && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      cycleSelect(target, -1);
      return true;
    }
  }

  if (!isTextInput && !event.shiftKey && (event.key === 'j' || event.key === 'k')) {
    event.preventDefault();
    if (modalEl) modalEl.scrollTop += event.key === 'j' ? 60 : -60;
    return true;
  }

  return false;
}
