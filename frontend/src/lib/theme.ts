export type ThemeMode = 'light' | 'dark' | 'system';

export function setTheme(mode: ThemeMode) {
  const root = typeof document !== 'undefined' ? document.documentElement : null;
  if (root) {
    if (mode === 'system') {
      root.removeAttribute('data-theme');
    } else {
      root.setAttribute('data-theme', mode);
    }
  }
}

export function getTheme(): ThemeMode {
  if (typeof document === 'undefined') return 'system';
  return (document.documentElement.getAttribute('data-theme') as ThemeMode) || 'system';
}
