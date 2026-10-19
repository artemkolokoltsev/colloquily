import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
} from "pdfjs-dist/legacy/build/pdf.mjs";
import worker from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url";
import { api, sourceBlob } from "../api/client";
import { ErrorNotice } from "./Common";
GlobalWorkerOptions.workerSrc = worker;
interface Note {
  page: number;
  content: string;
}
export function PdfReader({
  exam,
  document,
  close,
}: {
  exam: number;
  document: { id: number; title: string; relative_path: string };
  close: () => void;
}) {
  const { t } = useTranslation();
  const key = `colloquily.reader.${exam}.${document.id}`;
  const [pdf, setPdf] = useState<PDFDocumentProxy>();
  const [page, setPage] = useState(() =>
    Math.max(1, Number(localStorage.getItem(key)) || 1),
  );
  const [zoom, setZoom] = useState(1);
  const [width, setWidth] = useState(600);
  const [fit, setFit] = useState(true);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchStatus, setSearchStatus] = useState("");
  const canvas = useRef<HTMLCanvasElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const draftKey = `${key}.drafts`;
  const dirty = useRef(new Map<number, string>());
  const latest = useRef(new Map<number, string>());
  const pending = useRef(0);
  const chain = useRef<Promise<void>>(Promise.resolve());
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const mounted = useRef(true);
  function flush() {
    clearTimeout(timer.current);
    const edits = [...dirty.current];
    dirty.current.clear();
    const work = chain.current.then(async () => {
      for (let index = 0; index < edits.length; index++) {
        const [number, content] = edits[index];
        try {
          await api(
            `/exams/${exam}/documents/${document.id}/notes/${number}`,
            "PUT",
            { content },
          );
          const drafts = JSON.parse(localStorage.getItem(draftKey) || "{}");
          if (drafts[number] === content) {
            delete drafts[number];
            localStorage.setItem(draftKey, JSON.stringify(drafts));
          }
        } catch (e) {
          for (const [number, content] of edits.slice(index))
            if (
              !dirty.current.has(number) &&
              latest.current.get(number) === content
            )
              dirty.current.set(number, content);
          throw e;
        }
      }
    });
    chain.current = work.catch(() => undefined);
    return work;
  }
  async function commit() {
    pending.current += 1;
    setSaving(true);
    setError("");
    try {
      await flush();
      return true;
    } catch {
      setError(t("ui.noteSaveError"));
      return false;
    } finally {
      pending.current -= 1;
      if (mounted.current) setSaving(pending.current > 0);
    }
  }
  useEffect(() => {
    mounted.current = true;
    let active = true;
    let url = "";
    let task: ReturnType<typeof getDocument> | undefined;
    void Promise.all([
      sourceBlob(exam, document.relative_path).then(async (value) => {
        url = value;
        if (!active) {
          URL.revokeObjectURL(url);
          return;
        }
        task = getDocument({
          url,
          cMapUrl: "/pdfjs/cmaps/",
          cMapPacked: true,
          standardFontDataUrl: "/pdfjs/standard_fonts/",
          wasmUrl: "/pdfjs/wasm/",
        });
        const doc = await task.promise;
        if (active) {
          setPdf(doc);
          setPage((p) => Math.min(p, doc.numPages));
        }
      }),
      api<Note[]>(`/exams/${exam}/documents/${document.id}/notes`).then(
        (rows) => {
          if (active) {
            let drafts: Record<string, string> = {};
            try {
              drafts = JSON.parse(localStorage.getItem(draftKey) || "{}");
            } catch {
              /* Ignore malformed local recovery cache. */
            }
            setNotes({
              ...Object.fromEntries(rows.map((n) => [n.page, n.content])),
              ...drafts,
            });
            setLoaded(true);
            for (const [number, content] of Object.entries(drafts)) {
              dirty.current.set(Number(number), content);
              latest.current.set(Number(number), content);
            }
            if (dirty.current.size) void commit();
          }
        },
      ),
    ]).catch(() => {
      if (active) setError(t("ui.pdfError"));
    });
    return () => {
      active = false;
      mounted.current = false;
      void flush().catch(() => undefined);
      void task?.destroy();
      if (url) URL.revokeObjectURL(url);
    };
  }, [exam, document.id]);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(200, entries[0].contentRect.width - 32)),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!pdf) return;
    let active = true;
    let render:
      | ReturnType<Awaited<ReturnType<PDFDocumentProxy["getPage"]>>["render"]>
      | undefined;
    void pdf
      .getPage(page)
      .then((p) => {
        if (!active || !canvas.current) return;
        const base = p.getViewport({ scale: 1 });
        const view = p.getViewport({ scale: fit ? width / base.width : zoom });
        const target = canvas.current;
        target.width = view.width;
        target.height = view.height;
        render = p.render({ canvas: target, viewport: view });
        return render.promise;
      })
      .catch((e) => {
        if (active && e?.name !== "RenderingCancelledException")
          setError(t("ui.pdfError"));
      });
    localStorage.setItem(key, String(page));
    return () => {
      active = false;
      render?.cancel();
    };
  }, [pdf, page, zoom, fit, width]);
  async function go(number: number) {
    if (pdf && number >= 1 && number <= pdf.numPages && (await commit()))
      setPage(number);
  }
  async function search() {
    if (!pdf || !query.trim()) return;
    setSearching(true);
    setSearchStatus("");
    try {
      for (let offset = 1; offset <= pdf.numPages; offset++) {
        const number = ((page - 1 + offset) % pdf.numPages) + 1;
        const content = await (await pdf.getPage(number)).getTextContent();
        const text = content.items
          .map((item) => ("str" in item ? item.str : ""))
          .join(" ");
        if (
          text.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
        ) {
          await go(number);
          setSearchStatus(t("ui.searchFound", { page: number }));
          return;
        }
      }
      setSearchStatus(t("ui.noMatches"));
    } catch {
      setError(t("ui.pdfError"));
    } finally {
      setSearching(false);
    }
  }
  return (
    <article className="pdf-reader">
      <div className="page-heading">
        <h3>{document.title}</h3>
        <button
          onClick={async () => {
            if (await commit()) close();
          }}
        >
          {t("common.closeSource")}
        </button>
      </div>
      <ErrorNotice error={error} />
      {error && loaded && (
        <button onClick={() => void commit()}>{t("startup.retry")}</button>
      )}
      <div className="toolbar">
        <button
          disabled={!pdf || page <= 1 || saving}
          onClick={() => void go(page - 1)}
        >
          {t("ui.previousPage")}
        </button>
        <label>
          {t("ui.page")}
          <input
            type="number"
            min={1}
            max={pdf?.numPages || 1}
            value={page}
            disabled={!pdf || saving}
            onChange={(e) => void go(Number(e.target.value))}
          />
        </label>
        <span>/ {pdf?.numPages ?? "—"}</span>
        <button
          disabled={!pdf || page >= pdf.numPages || saving}
          onClick={() => void go(page + 1)}
        >
          {t("ui.nextPage")}
        </button>
        <button
          onClick={() => {
            setFit(false);
            setZoom((z) => Math.max(0.25, z - 0.25));
          }}
          aria-label={t("ui.zoomOut")}
        >
          −
        </button>
        <button
          onClick={() => {
            setFit(false);
            setZoom((z) => Math.min(4, z + 0.25));
          }}
          aria-label={t("ui.zoomIn")}
        >
          +
        </button>
        <button aria-pressed={fit} onClick={() => setFit(true)}>
          {t("ui.fitWidth")}
        </button>
      </div>
      <form
        className="toolbar"
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
      >
        <input
          aria-label={t("ui.searchPdf")}
          placeholder={t("ui.searchPdf")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button disabled={!pdf || searching}>{t("ui.findNext")}</button>
        <span role="status">{searchStatus}</span>
      </form>
      {!pdf && !error && <p role="status">{t("ui.loadingPdf")}</p>}
      <div className="reader-layout">
        <div className="pdf-canvas" ref={viewport}>
          <canvas ref={canvas} aria-label={t("ui.pdfPage", { page })} />
        </div>
        <div className="page-notes">
          <label>
            {t("ui.pageNote", { page })}
            <textarea
              disabled={!loaded}
              value={notes[page] || ""}
              placeholder={t("ui.addNote")}
              onChange={(e) => {
                const content = e.target.value;
                setNotes((n) => ({ ...n, [page]: content }));
                dirty.current.set(page, content);
                latest.current.set(page, content);
                setSaving(true);
                try {
                  const drafts = JSON.parse(
                    localStorage.getItem(draftKey) || "{}",
                  );
                  drafts[page] = content;
                  localStorage.setItem(draftKey, JSON.stringify(drafts));
                } catch {
                  setError(t("ui.noteSaveError"));
                }
                clearTimeout(timer.current);
                timer.current = setTimeout(() => void commit(), 600);
              }}
              onBlur={() => void commit()}
            />
          </label>
          <p role="status">
            {saving ? t("ui.savingNote") : t("ui.notesAutosave")}
          </p>
          <p className="muted">{t("ui.notesPrivate")}</p>
          <div className="toolbar">
            {Object.entries(notes)
              .filter(([, text]) => text.trim())
              .map(([number]) => (
                <button key={number} onClick={() => void go(Number(number))}>
                  {t("ui.page")} {number} •
                </button>
              ))}
          </div>
        </div>
      </div>
    </article>
  );
}
