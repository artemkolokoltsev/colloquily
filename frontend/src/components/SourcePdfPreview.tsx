import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
} from "pdfjs-dist/legacy/build/pdf.mjs";
import worker from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url";
import { sourceBytes } from "../api/client";
GlobalWorkerOptions.workerSrc = worker;

export default function SourcePdfPreview({
  exam,
  path,
  page,
}: {
  exam: number;
  path: string;
  page: number;
}) {
  const { t } = useTranslation();
  const [pdf, setPdf] = useState<PDFDocumentProxy>();
  const [error, setError] = useState(false);
  const [ready, setReady] = useState(false);
  const [retry, setRetry] = useState(0);
  const [width, setWidth] = useState(600);
  const [zoom, setZoom] = useState(false);
  const holder = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    let active = true;
    let task: ReturnType<typeof getDocument> | undefined;
    setPdf(undefined);
    setError(false);
    setReady(false);
    void sourceBytes(exam, path)
      .then(async (data) => {
        if (!active) return;
        task = getDocument({
          data,
          cMapUrl: new URL("/pdfjs/cmaps/", location.href).href,
          cMapPacked: true,
          standardFontDataUrl: new URL("/pdfjs/standard_fonts/", location.href)
            .href,
          wasmUrl: new URL("/pdfjs/wasm/", location.href).href,
        });
        const document = await task.promise;
        if (page < 1 || page > document.numPages)
          throw new Error("Invalid cited page");
        if (active) setPdf(document);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
      void task?.destroy();
    };
  }, [exam, path, page, retry]);
  useEffect(() => {
    if (!holder.current) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(200, entries[0].contentRect.width)),
    );
    observer.observe(holder.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!pdf) return;
    let active = true;
    let rendering:
      | ReturnType<Awaited<ReturnType<PDFDocumentProxy["getPage"]>>["render"]>
      | undefined;
    setReady(false);
    void pdf
      .getPage(page)
      .then(async (source) => {
        if (!active || !canvas.current) return;
        const target = canvas.current;
        const scale =
          (width / source.getViewport({ scale: 1 }).width) * (zoom ? 1.5 : 1);
        const ratio = Math.min(devicePixelRatio || 1, 2);
        const viewport = source.getViewport({ scale: scale * ratio });
        target.width = viewport.width;
        target.height = viewport.height;
        target.style.width = `${viewport.width / ratio}px`;
        target.style.height = `${viewport.height / ratio}px`;
        rendering = source.render({ canvas: target, viewport });
        await rendering.promise;
        if (active) setReady(true);
      })
      .catch((e) => {
        if (active && e?.name !== "RenderingCancelledException") setError(true);
      });
    return () => {
      active = false;
      rendering?.cancel();
    };
  }, [pdf, page, width, zoom]);
  return (
    <div className="insight-pdf">
      <div className="insight-pdf-toolbar">
        <span>
          {t("ui.insightPage", { page, total: pdf?.numPages || "…" })}
        </span>
        <button onClick={() => setZoom(!zoom)} aria-pressed={zoom}>
          {t(zoom ? "ui.insightFit" : "ui.insightZoom")}
        </button>
      </div>
      {error ? (
        <p role="alert">
          {t("ui.insightPdfError")}{" "}
          <button onClick={() => setRetry(retry + 1)}>
            {t("ui.insightRetry")}
          </button>
        </p>
      ) : (
        !ready && <p role="status">{t("ui.insightLoading")}</p>
      )}
      <div ref={holder} className="insight-pdf-viewport">
        <canvas
          ref={canvas}
          hidden={!ready || error}
          role="img"
          aria-label={t("ui.insightPage", {
            page,
            total: pdf?.numPages || "…",
          })}
        />
      </div>
    </div>
  );
}
