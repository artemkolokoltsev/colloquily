import { useState, type ReactNode } from "react";

export function PagedTable<T>({
  rows,
  headers,
  renderRow,
  label,
  resetKey = "",
}: {
  rows: T[];
  headers: string[];
  renderRow: (row: T) => ReactNode;
  label: string;
  resetKey?: string;
}) {
  const [selection, setSelection] = useState({ key: resetKey, page: 1 });
  if (selection.key !== resetKey) {
    setSelection({ key: resetKey, page: 1 });
  }
  const pages = Math.max(1, Math.ceil(rows.length / 10));
  const page = Math.min(selection.key === resetKey ? selection.page : 1, pages);
  const start = (page - 1) * 10;
  return (
    <div className="paged-table">
      <div className="table-scroll">
        <table>
          <caption className="sr-only">{label}</caption>
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h} scope="col">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{rows.slice(start, start + 10).map(renderRow)}</tbody>
        </table>
      </div>
      {!rows.length && (
        <p className="empty-state">No {label.toLowerCase()} match this view.</p>
      )}
      <nav className="table-pagination" aria-label={`${label} pagination`}>
        <span role="status">
          {rows.length
            ? `${start + 1}–${Math.min(start + 10, rows.length)} of ${rows.length}`
            : "0 results"}
        </span>
        <div>
          <button
            disabled={page === 1}
            onClick={() => setSelection({ key: resetKey, page: page - 1 })}
          >
            Previous
          </button>
          <span>
            Page {page} of {pages}
          </span>
          <button
            disabled={page === pages}
            onClick={() => setSelection({ key: resetKey, page: page + 1 })}
          >
            Next
          </button>
        </div>
      </nav>
    </div>
  );
}
