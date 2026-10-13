/** Shared pagination for question libraries, review queues, and progress tables. */
export function tablePage<T>(rows: T[], requestedPage: number, size = 10) {
  if (!Number.isInteger(size) || size < 1) throw new RangeError('Invalid page size');
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const page = Math.max(1, Math.min(Math.trunc(requestedPage) || 1, pages));
  const start = (page - 1) * size;
  return { pages, page, start, rows: rows.slice(start, start + size) };
}
