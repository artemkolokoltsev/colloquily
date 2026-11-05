import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { materialReviewPage } from "../api/client";
import { ErrorNotice, Sources } from "../components/Common";
import { StudyText } from "../components/StudyText";
import type { MaterialReviewPage, MaterialUnit } from "../types";

/** Only the visible page of evidence is fetched and mounted. */
export function MaterialReview({
  exam,
  documentId,
  revision,
  busy,
  save,
  technical = false,
}: {
  exam: number;
  documentId?: number;
  revision: number;
  busy: boolean;
  technical?: boolean;
  save: (unit: MaterialUnit, status: string, content: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<MaterialReviewPage>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [dirty, setDirty] = useState<Set<number>>(new Set());
  const navigation = useRef<HTMLDivElement>(null);
  const markDirty = useCallback((id: number, changed: boolean) => {
    setDirty((previous) => {
      if (previous.has(id) === changed) return previous;
      const next = new Set(previous);
      if (changed) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void materialReviewPage(exam, documentId, offset, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        if (offset && offset >= value.total) {
          setOffset(
            Math.max(0, Math.ceil(value.total / value.limit) - 1) * value.limit,
          );
        } else setPage(value);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [exam, documentId, offset, revision, retry]);
  function navigate(next: number) {
    setPage(undefined);
    setOffset(next);
    navigation.current?.scrollIntoView({ block: "start" });
    navigation.current?.focus({ preventScroll: true });
  }
  return (
    <section className="material-review" aria-label={t("ui.materialPassages")}>
      <div
        className="review-navigation"
        role="group"
        aria-label={t("ui.materialNavigation")}
        tabIndex={-1}
        ref={navigation}
      >
        <button
          disabled={busy || loading || !!dirty.size || !offset}
          onClick={() => navigate(Math.max(0, offset - 10))}
        >
          {t("ui.materialPrevious")}
        </button>
        <span role="status">
          {page
            ? t("ui.materialRange", {
                start: page.total ? offset + 1 : 0,
                end: Math.min(offset + page.items.length, page.total),
                total: page.total,
              })
            : t("ui.courseLoading")}
        </span>
        <button
          disabled={
            busy ||
            loading ||
            !!dirty.size ||
            !page ||
            offset + page.items.length >= page.total
          }
          onClick={() => navigate(offset + 10)}
        >
          {t("ui.materialNext")}
        </button>
      </div>
      {!!dirty.size && <p role="status">{t("ui.materialUnsaved")}</p>}
      <ErrorNotice error={error} />
      {error && (
        <button onClick={() => setRetry((value) => value + 1)}>
          {t("ui.insightRetry")}
        </button>
      )}
      {loading && <p role="status">{t("ui.courseLoading")}</p>}
      {page && !page.total && <p>{t("ui.s6adfed4d6a")}</p>}
      {page?.items.map((unit) => (
        <MaterialPassage
          key={`${unit.id}:${unit.content}:${unit.review_status}`}
          unit={unit}
          exam={exam}
          busy={busy || loading}
          save={save}
          markDirty={markDirty}
          technical={technical}
        />
      ))}
    </section>
  );
}

function MaterialPassage({
  unit,
  exam,
  busy,
  save,
  markDirty,
  technical,
}: {
  unit: MaterialUnit;
  exam: number;
  busy: boolean;
  technical: boolean;
  save: (unit: MaterialUnit, status: string, content: string) => Promise<void>;
  markDirty: (id: number, dirty: boolean) => void;
}) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(unit.content);
  const [sourceOpen, setSourceOpen] = useState(false);
  useEffect(() => () => markDirty(unit.id, false), [unit.id, markDirty]);
  const outline = unit.study_problem === "outline_without_explanation";
  const unusable =
    !!unit.study_problem ||
    ["quarantined", "rejected"].includes(unit.review_status);
  return (
    <article className="evidence-snippet" data-unit-id={unit.id}>
      <strong>
        {technical ? `${unit.document_title} · ` : ""}
        {unit.source_location.replace(/,\s*lines?\s*\d+-\d+/i, "")}
      </strong>
      <span className="status-badge">
        {t(
          outline
            ? "ui.materialOutline"
            : unusable
              ? "ui.redesignUnusable"
              : unit.review_status === "accepted"
                ? "ui.redesignReady"
                : "ui.redesignReview",
        )}
      </span>
      {editing ? (
        <label>
          {t("ui.redesignEditContent")}
          <p className="muted">{t("ui.mathHelp")}</p>
          <StudyText preserveLines>{content}</StudyText>
          <textarea
            value={content}
            disabled={busy}
            onChange={(event) => {
              setContent(event.target.value);
              markDirty(unit.id, event.target.value !== unit.content);
            }}
          />
        </label>
      ) : (
        <StudyText preserveLines>{unit.content}</StudyText>
      )}
      {(outline || unit.review_status !== "accepted") && (
        <p className="muted">
          {t(
            outline
              ? "ui.materialOutlineReason"
              : unusable
                ? "ui.redesignUnusableReason"
                : "ui.redesignReviewReason",
          )}
        </p>
      )}
      <details
        className="material-source"
        onToggle={(event) => setSourceOpen(event.currentTarget.open)}
      >
        <summary>{t("ui.materialOriginal")}</summary>
        {sourceOpen && (
          <Sources exam={exam} sources={[{ ...unit, id: undefined }]} />
        )}
      </details>
      <div className="toolbar">
        <button
          disabled={busy}
          onClick={() => {
            if (editing) {
              setContent(unit.content);
              markDirty(unit.id, false);
            }
            setEditing(!editing);
          }}
        >
          {t(editing ? "ui.materialCancelEdit" : "ui.redesignEditContent")}
        </button>
        <button
          disabled={
            busy ||
            !content.trim() ||
            (unusable && content.trim() === unit.content.trim())
          }
          onClick={() => void save(unit, "accepted", content)}
        >
          {t("ui.redesignConfirmReady")}
        </button>
        {technical && (
          <button
            disabled={busy}
            onClick={() => void save(unit, "needs_review", content)}
          >
            {t("ui.redesignReview")}
          </button>
        )}
        <button
          disabled={busy}
          onClick={() => void save(unit, "rejected", content)}
        >
          {t("ui.redesignDoNotUse")}
        </button>
      </div>
    </article>
  );
}
