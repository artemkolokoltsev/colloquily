/** PDF viewers use one-based page anchors; Markdown sources have no anchor. */
export function sourcePage(source: { source_start?: number; source_location?: string }): number | undefined {
  const explicit = source.source_start;
  if (explicit && Number.isInteger(explicit) && explicit > 0) return explicit;
  const match = /\b(?:page|slide|seite)\s+(\d+)\b/i.exec(source.source_location || '');
  const page = match ? Number(match[1]) : 0;
  return page > 0 ? page : undefined;
}
