/** Only enumerated genre values are UI chrome. Preserve all unknown author text. */
export function genreLabel(value: string | null | undefined, labels: Record<string, string>, empty: string): string {
  if (!value) return empty;
  return Object.prototype.hasOwnProperty.call(labels, value) ? labels[value] : value;
}
