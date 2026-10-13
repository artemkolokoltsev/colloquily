import { useTranslation } from "react-i18next";
import { useState, type ReactNode } from "react";
import { tablePage } from './tablePage';

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
  const { t } = useTranslation();
  const [selection, setSelection] = useState({ key: resetKey, page: 1 });
  if (selection.key !== resetKey) {
    setSelection({ key: resetKey, page: 1 });
  }
  const { pages, page, start, rows: visibleRows } = tablePage(rows, selection.key === resetKey ? selection.page : 1);
  return (
    <div className="paged-table">
      <div className="table-scroll">
        <table>
          <caption className="sr-only">{label}</caption>
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h} scope="col">
                  {t(`dynamic.${h}`, { defaultValue: h })}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{visibleRows.map(renderRow)}</tbody>
        </table>
      </div>
      {!rows.length && (
        <p className="empty-state">{t('ui.s1ea442a134')} {label.toLowerCase()} {t('ui.sac686793c4')}</p>
      )}
      <nav className="table-pagination" aria-label={`${label} pagination`}>
        <span role="status">
          {rows.length
            ? t('dynamic.pagination', { start: start + 1, end: Math.min(start + 10, rows.length), total: rows.length })
            : t('ui.sff7009f4a9')}
        </span>
        <div>
          <button
            disabled={page === 1}
            onClick={() => setSelection({ key: resetKey, page: page - 1 })}
          > {t('ui.sa57b08a480')} </button>
          <span> {t('ui.s0a30a815d6')} {page} {t('ui.s28391d3bc6')} {pages}
          </span>
          <button
            disabled={page === pages}
            onClick={() => setSelection({ key: resetKey, page: page + 1 })}
          > {t('ui.s1ff57a29d7')} </button>
        </div>
      </nav>
    </div>
  );
}
