import type { Source } from '$lib/types';

export const SOURCE_COLOR_PALETTE = [
  '#2563eb',
  '#059669',
  '#ea580c',
  '#dc2626',
  '#7c3aed',
  '#0d9488',
  '#b45309',
  '#db2777',
] as const;

export function defaultSourceColor(index: number): string {
  return SOURCE_COLOR_PALETTE[index % SOURCE_COLOR_PALETTE.length];
}

export function sourceColorForIndex(source: Source, index: number): string {
  return source.color || defaultSourceColor(index);
}

export function sourceColorMap(sources: Source[]): Record<string, string> {
  return Object.fromEntries(sources.map((source, index) => [source.id, sourceColorForIndex(source, index)]));
}
