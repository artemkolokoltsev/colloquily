import { StudyText } from "../components/StudyText";
import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import { lazy, Suspense } from "react";
const PdfReader = lazy(() =>
  import("../components/PdfReader").then((module) => ({
    default: module.PdfReader,
  })),
);
import { api, operation } from "../api/client";
import { ErrorNotice, Progress, Sources } from "../components/Common";
import type { Job } from "../types";
interface Unit {
  id: number;
  document_id: number;
  content: string;
  review_status: string;
  document_title: string;
  relative_path: string;
  source_location: string;
  source_start?: number;
  quality_problems?: string[];
}
interface MaterialsData {
  raw: string[];
  documents: {
    id: number;
    title: string;
    relative_path: string;
    processing_status?: string;
    accepted_count?: number;
    review_count?: number;
    created_at?: string;
    extraction?: {
      state?: string;
      pages_processed?: number;
      pages_total?: number;
      empty_pages?: number[];
    };
  }[];
  processing?: {
    status: string;
    progress_percent: number;
    current_document?: string;
    error_text?: string;
  };
}
export function Materials({
  exam,
  onPractice,
  onSetup,
}: {
  exam: number;
  onPractice: () => void;
  onSetup: () => void;
}) {
  const { t } = useTranslation();
  const [preparation, setPreparation] = useState<{
    job: Job | null;
    questions: number;
    coverage?: {
      document_id: number;
      topic_id: number | null;
      target: number;
      covered: number;
      generated: number;
    }[];
  }>();
  const [reader, setReader] = useState<MaterialsData["documents"][number]>();
  const [advanced, setAdvanced] = useState(false);
  const [data, setData] = useState<MaterialsData>();
  const [units, setUnits] = useState<Unit[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [mode, setMode] = useState("fast");
  const [reviewDocument, setReviewDocument] = useState<number | null>(null);
  const [questions, setQuestions] = useState<{ evidence_ids?: number[] }[]>([]);
  async function refresh() {
    const [d, u, p, q] = await Promise.all([
      api<MaterialsData>(`/exams/${exam}/documents`),
      advanced ? api<Unit[]>(`/exams/${exam}/review`) : Promise.resolve([]),
      api<{ job: Job | null; questions: number }>(`/exams/${exam}/preparation`),
      advanced
        ? api<{ evidence_ids?: number[] }[]>(`/exams/${exam}/questions`)
        : Promise.resolve([]),
    ]);
    setData(d);
    setUnits(u);
    setPreparation(p);
    setQuestions(q);
  }
  useEffect(() => {
    void refresh().catch((e) => setError(String(e)));
    const timer = setInterval(() => {
      if (
        ["queued", "running"].includes(preparation?.job?.status || "") ||
        ["queued", "running"].includes(data?.processing?.status || "")
      )
        void refresh().catch((e) => setError(String(e)));
    }, 2500);
    return () => clearInterval(timer);
  }, [exam, advanced, preparation?.job?.status, data?.processing?.status]);
  async function act(work: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await work();
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const preparing = ["queued", "running"].includes(
    preparation?.job?.status || "",
  );
  const processing = ["queued", "running"].includes(
    data?.processing?.status || "",
  );
  return (
    <section>
      <p className="eyebrow">{t("ui.sac2cb8bf2e")}</p>
      <h2>{t("nav.materials")}</h2>
      <p>{t("ui.libraryIntro")}</p>
      <ErrorNotice error={error} />
      {preparing && <Progress job={preparation?.job || null} />}
      <label>
        {" "}
        {t("ui.s9098f1f65b")}{" "}
        <input
          disabled={busy || preparing || processing}
          type="file"
          multiple
          accept=".pdf,.md,.markdown"
          onChange={(e) => {
            const files = e.target.files;
            if (!files?.length) return;
            const form = new FormData();
            Array.from(files).forEach((f) => form.append("files", f));
            void act(async () => {
              await api(`/exams/${exam}/documents`, "POST", form);
              const readiness = await api<{ state: string }>(
                `/exams/${exam}/models/readiness`,
              );
              if (readiness.state === "ready")
                await api(`/exams/${exam}/prepare`, "POST", {});
              else
                await api(`/exams/${exam}/process`, "POST", {
                  mode: "deterministic",
                });
            });
            e.target.value = "";
          }}
        />
      </label>
      {reader && (
        <Suspense fallback={<p role="status">{t("ui.loadingPdf")}</p>}>
          <PdfReader
            key={`${exam}:${reader.id}`}
            exam={exam}
            document={reader}
            close={() => setReader(undefined)}
          />
        </Suspense>
      )}
      {data && !data.raw.length && <p>{t("ui.s579041d84b")}</p>}
      <div className="document-grid">
        {data?.documents.map((document) => {
          const passages = units.filter(
            (unit) => unit.document_id === document.id,
          );
          const ready = document.accepted_count || 0;
          const review = document.review_count || 0;
          const ids = new Set(passages.map((unit) => unit.id));
          return (
            <article key={document.id}>
              <h3>{document.title}</h3>
              <button
                disabled={busy || processing}
                onClick={() =>
                  void act(async () => {
                    const passages = await api<Unit[]>(
                      `/exams/${exam}/review?document_id=${document.id}`,
                    );
                    if (!passages.length) throw new Error(t("ui.noStudyText"));
                    const text = passages
                      .sort(
                        (a, b) =>
                          (a.source_start || 0) - (b.source_start || 0) ||
                          a.id - b.id,
                      )
                      .map(
                        (unit) =>
                          `## ${unit.source_location} · ${unit.review_status}\n\n${unit.content}`,
                      )
                      .join("\n\n");
                    const url = URL.createObjectURL(
                      new Blob([`# ${document.title}\n\n${text}`], {
                        type: "text/markdown;charset=utf-8",
                      }),
                    );
                    const link = window.document.createElement("a");
                    link.href = url;
                    link.download = "study-text.md";
                    link.click();
                    setTimeout(() => URL.revokeObjectURL(url), 1000);
                  })
                }
              >
                {t("ui.exportStudyText")}
              </button>
              <span className="status-badge">
                {t(
                  document.processing_status === "raw"
                    ? processing
                      ? "ui.processingDocument"
                      : "ui.importedDocument"
                    : ready
                      ? "ui.redesignReady"
                      : review
                        ? "ui.redesignReview"
                        : "ui.redesignUnusable",
                )}
              </span>
              {advanced && (
                <p>
                  {t("ui.redesignDocumentSummary", {
                    pages:
                      document.extraction?.pages_processed ??
                      new Set(
                        passages
                          .map((unit) => unit.source_start)
                          .filter(Boolean),
                      ).size,
                    ready,
                    review,
                    unusable: passages.length - ready - review,
                    questions: questions.filter((question) =>
                      question.evidence_ids?.some((id) => ids.has(id)),
                    ).length,
                  })}
                </p>
              )}
              {document.extraction?.state === "extraction_failed" && (
                <p className="error">{t("ui.redesignExtractionFailed")}</p>
              )}
              {document.extraction?.state === "no_extractable_text" && (
                <p>{t("ui.redesignNoText")}</p>
              )}
              {!!document.extraction?.empty_pages?.length && (
                <p className="muted">
                  {t("ui.redesignEmptyPages", {
                    pages: document.extraction.empty_pages.join(", "),
                  })}
                </p>
              )}
              {document.relative_path.toLowerCase().endsWith(".pdf") && (
                <button className="primary" onClick={() => setReader(document)}>
                  {t("ui.openPdf")}
                </button>
              )}
              <p className="muted">
                {document.extraction?.pages_total ??
                  document.extraction?.pages_processed ??
                  "—"}{" "}
                {t("ui.pages")} ·{" "}
                {document.created_at
                  ? new Date(document.created_at).toLocaleDateString()
                  : "—"}
              </p>
              <details>
                <summary>{t("ui.details")}</summary>
                <button
                  onClick={() => {
                    setAdvanced(true);
                    setReviewDocument(
                      reviewDocument === document.id ? null : document.id,
                    );
                  }}
                  aria-expanded={reviewDocument === document.id}
                >
                  {t("ui.redesignReviewContent")}
                </button>
                <button
                  disabled={busy || preparing || processing}
                  onClick={() =>
                    void act(() =>
                      api(`/exams/${exam}/process`, "POST", {
                        mode: "deterministic",
                        relative_path: document.relative_path,
                        force: true,
                      }),
                    )
                  }
                >
                  {t("ui.redesignReprocess")}
                </button>
                {reviewDocument === document.id &&
                  passages.map((unit) => (
                    <StudentEvidence
                      key={`${unit.id}:${unit.content}:${unit.review_status}`}
                      unit={unit}
                      exam={exam}
                      busy={busy || preparing || processing}
                      save={(status, content) =>
                        act(() =>
                          api(`/exams/${exam}/review/${unit.id}`, "PATCH", {
                            status,
                            content,
                          }),
                        )
                      }
                    />
                  ))}
              </details>
            </article>
          );
        })}
      </div>
      <details open>
        <summary>{t("ui.practicePreparation")}</summary>
        <article className="preparation-card">
          <h3>
            {preparing
              ? t("ui.s86565c9c89")
              : preparation?.questions
                ? t("ui.s40b3761cb8")
                : t("ui.s34ef570432")}
          </h3>
          <p> {t("ui.s0650bb8705")} </p>
          <button
            className="primary"
            disabled={busy || preparing || processing || !data?.raw.length}
            onClick={() =>
              act(async () => {
                const readiness = await api<{ state: string }>(
                  `/exams/${exam}/models/readiness`,
                );
                if (readiness.state !== "ready") {
                  onSetup();
                  return;
                }
                return api(`/exams/${exam}/prepare`, "POST");
              })
            }
          >
            {preparation?.job?.status === "failed"
              ? t("ui.s8c029bc7ca")
              : preparation?.questions
                ? t("ui.redesignFillCoverage")
                : t("ui.s80a7b9c840")}
          </button>
          {!!preparation?.questions && (
            <button className="primary" onClick={onPractice}>
              {" "}
              {t("ui.sc69f851732")}{" "}
            </button>
          )}
          <Progress job={preparation?.job || null} />
          {!!preparation?.coverage?.length && (
            <p>
              {t("ui.redesignCoverage", {
                complete: preparation.coverage.filter(
                  (item) => item.covered + item.generated >= item.target,
                ).length,
                total: preparation.coverage.length,
              })}
            </p>
          )}
          {!!preparation?.questions &&
            preparation.coverage?.some(
              (item) => item.covered + item.generated < item.target,
            ) && <p role="status">{t("ui.redesignPartialCoverage")}</p>}
          {preparation?.job?.status === "failed" && (
            <>
              <ErrorNotice
                error={preparation.job.error || t("ui.sab42b805f9")}
              />
              <button onClick={onSetup}>{t("ui.s7932a732e4")}</button>
            </>
          )}
        </article>
      </details>
      <details onToggle={(e) => setAdvanced(e.currentTarget.open)}>
        <summary>{t("ui.sc933415600")}</summary>
        <p className="muted"> {t("ui.s29f1fc0e10")} </p>
        <div className="toolbar">
          <select
            aria-label={t("ui.s25aaa653a5")}
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="fast">{t("ui.s5d28dddc38")}</option>
            <option value="deep">{t("ui.s938c8b62b7")}</option>
            <option value="deterministic">{t("ui.s29aa06dc22")}</option>
          </select>
          <button
            disabled={
              busy ||
              ["queued", "running"].includes(data?.processing?.status || "")
            }
            onClick={() =>
              act(() => api(`/exams/${exam}/process`, "POST", { mode }))
            }
          >
            {" "}
            {t("ui.s9ba15dba5c")}{" "}
          </button>
          <button
            disabled={busy || preparing || processing}
            onClick={() =>
              act(() => api(`/exams/${exam}/process/retry`, "POST"))
            }
          >
            {" "}
            {t("ui.s2c4517af49")}{" "}
          </button>
          <button
            disabled={busy || preparing || processing}
            onClick={() =>
              act(() => operation(`/exams/${exam}/index`, {}, setJob))
            }
          >
            {" "}
            {t("ui.s0c123f1916")}{" "}
          </button>
        </div>
        {data?.processing && (
          <div role="status">
            <p>
              {data.processing.status} · {data.processing.current_document}
            </p>
            <progress max="100" value={data.processing.progress_percent} />
            <ErrorNotice error={data.processing.error_text || ""} />
          </div>
        )}
        <Progress job={job} />
        <h3>{t("ui.sbcb9c2e713")}</h3>
        {!units.length && <p>{t("ui.s6adfed4d6a")}</p>}
        {units.map((unit) => (
          <article key={unit.id}>
            <strong>
              {unit.document_title} · {unit.source_location}
            </strong>
            <span>{unit.review_status}</span>
            <textarea
              aria-label={t("ui.sef57bb58eb")}
              defaultValue={unit.content}
              key={`${unit.id}:${unit.content}`}
              onBlur={(e) => {
                if (e.target.value !== unit.content)
                  void act(() =>
                    api(`/exams/${exam}/review/${unit.id}`, "PATCH", {
                      status: unit.review_status,
                      content: e.target.value,
                    }),
                  );
              }}
            />
            <div className="toolbar">
              {["accepted", "needs_review", "rejected"].map((status) => (
                <button
                  disabled={busy || preparing || processing}
                  key={status}
                  onClick={() =>
                    act(() =>
                      api(`/exams/${exam}/review/${unit.id}`, "PATCH", {
                        status,
                      }),
                    )
                  }
                >
                  {status.replace("_", " ")}
                </button>
              ))}
            </div>
            <Sources exam={exam} sources={[unit]} technical />
          </article>
        ))}
      </details>
    </section>
  );
}

function StudentEvidence({
  unit,
  exam,
  busy,
  save,
}: {
  unit: Unit;
  exam: number;
  busy: boolean;
  save: (status: string, content: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(unit.content);
  const unusable = ["quarantined", "rejected"].includes(unit.review_status);
  return (
    <div className="evidence-snippet">
      <strong>
        {unit.source_location.replace(/,\s*lines?\s*\d+-\d+/i, "")}
      </strong>
      <span className="status-badge">
        {t(
          unit.review_status === "accepted"
            ? "ui.redesignReady"
            : unusable
              ? "ui.redesignUnusable"
              : "ui.redesignReview",
        )}
      </span>
      {editing ? (
        <label>
          {t("ui.redesignEditContent")}
          <p className="muted">{t("ui.mathHelp")}</p>
          <StudyText>{content}</StudyText>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            disabled={busy}
          />
        </label>
      ) : (
        <StudyText>{unit.content}</StudyText>
      )}
      {unit.review_status !== "accepted" && (
        <p className="muted">
          {t(
            unusable ? "ui.redesignUnusableReason" : "ui.redesignReviewReason",
          )}
        </p>
      )}
      <Sources exam={exam} sources={[{ ...unit, id: undefined }]} />
      <button disabled={busy} onClick={() => setEditing(!editing)}>
        {t("ui.redesignEditContent")}
      </button>
      <button
        disabled={
          busy ||
          !content.trim() ||
          (unusable && content.trim() === unit.content.trim())
        }
        onClick={() => void save("accepted", content)}
      >
        {t("ui.redesignConfirmReady")}
      </button>
      <button disabled={busy} onClick={() => void save("rejected", content)}>
        {t("ui.redesignDoNotUse")}
      </button>
    </div>
  );
}
