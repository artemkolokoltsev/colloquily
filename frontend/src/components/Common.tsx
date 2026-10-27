import { evaluationPresentation } from "./evaluationPresentation";
import { StudyText } from "./StudyText";
import { lazy, Suspense, useState } from "react";
const SourcePdfPreview = lazy(() => import("./SourcePdfPreview"));
import type { Evaluation, Job, Source } from "../types";
import { useTranslation } from "react-i18next";
import { sourcePage } from "./sourcePage";
export function ErrorNotice({ error }: { error: string }) {
  return error ? (
    <p role="alert" className="error">
      {error}
    </p>
  ) : null;
}
export function Progress({ job }: { job: Job | null }) {
  const { t } = useTranslation();
  if (!job) return null;
  if (job.status === "completed")
    return (
      <p className="job-complete" role="status">
        <span aria-hidden="true">✓ </span>
        {t("common.completed")}
      </p>
    );
  const fraction =
    job.total && job.total > 0
      ? Math.min(1, Math.max(0, (job.completed || 0) / job.total))
      : undefined;
  return (
    <div role="status" className="progress">
      <strong>
        {job.status === "completed"
          ? `${t("common.completed")} · `
          : job.status === "failed"
            ? `${t("common.failed")} · `
            : ""}
        {job.phase === "questions" && ["queued", "running"].includes(job.status)
          ? t("ui.redesignGenerationProgress", {
              processed: job.completed || 0,
              total: job.total || 0,
              candidates: job.candidates || 0,
              accepted: job.accepted || 0,
              rejected: job.rejected || 0,
            })
          : job.message || job.status}
      </strong>
      {job.status !== "failed" && (
        <progress
          aria-label={job.message || t("ui.progressWorking")}
          max={100}
          value={fraction === undefined ? undefined : fraction * 100}
        />
      )}
      {!!job.total && (
        <small>
          {Math.round((fraction || 0) * 100)}% ·{" "}
          {job.total > 1000000
            ? `${((job.completed || 0) / 1e9).toFixed(2)} / ${(job.total / 1e9).toFixed(2)} GB`
            : `${job.completed || 0} / ${job.total}`}
        </small>
      )}
    </div>
  );
}
export function EvaluationView({
  value,
  answer,
}: {
  value: Evaluation | null;
  answer?: string;
}) {
  const { t } = useTranslation();
  if (!value) return null;
  const feedback = evaluationPresentation(value);
  const ungraded = ["pending", "needs_review", "internal_error"].includes(
    value.status || "",
  );
  const skipped = value.status === "skipped";
  const score = ungraded || skipped ? null : value.score;
  return (
    <div className="answer-review">
      {answer !== undefined && (
        <section className="submitted-answer">
          <h4>{t("ui.resultsYourAnswer")}</h4>
          <StudyText>{answer || t("ui.resultsNoAnswer")}</StudyText>
        </section>
      )}
      <article
        className={`evaluation-card score-${ungraded || skipped ? "skipped" : (score ?? 0) < 2 ? "low" : (score ?? 0) < 4 ? "partial" : "strong"}`}
      >
        <h3>
          {t("common.answerFeedback")}
          {score != null && ` · ${score}/5`}
        </h3>
        {(ungraded || skipped) && (
          <p>
            {t(
              skipped
                ? "ui.resultsSkipped"
                : value.status === "pending"
                  ? "ui.pendingEvaluation"
                  : "ui.resultsUngradedNote",
            )}
          </p>
        )}
        {!ungraded && !skipped && (
          <>
            {(["correct", "missing", "incorrect"] as const).map(
              (key) =>
                feedback[key].length > 0 && (
                  <section key={key}>
                    <h4>{t(`common.${key}`)}</h4>
                    <ul>
                      {feedback[key].map((text, i) => (
                        <li key={i}>
                          <StudyText>{text}</StudyText>
                        </li>
                      ))}
                    </ul>
                  </section>
                ),
            )}
            {feedback.expected.length > 0 && (
              <details>
                <summary>{t("ui.expectedPoints")}</summary>
                <ul>
                  {feedback.expected.map((text, i) => (
                    <li key={i}>
                      <StudyText>{text}</StudyText>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {feedback.modelAnswer && (
              <details>
                <summary>{t("ui.feedbackModelAnswer")}</summary>
                <StudyText>{feedback.modelAnswer}</StudyText>
              </details>
            )}
          </>
        )}
        {value.subject_id && !!value.sources?.length && (
          <details>
            <summary>{t("ui.insight")}</summary>
            <Sources exam={value.subject_id} sources={value.sources} />
          </details>
        )}
      </article>
    </div>
  );
}
export function Sources({
  exam,
  sources,
  technical = false,
}: {
  exam: number;
  sources: Source[];
  technical?: boolean;
}) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState(0);
  const source = sources[Math.min(selected, sources.length - 1)];
  if (!source) return null;
  const path = source.relative_path || source.doc_name;
  const page = sourcePage(source);
  const pdf = path?.toLowerCase().endsWith(".pdf");
  return (
    <section className="source-insight" aria-label={t("ui.insight")}>
      {sources.length > 1 && (
        <div
          className="insight-tabs"
          role="group"
          aria-label={t("ui.insightChooseSource")}
        >
          {sources.map((item, i) => (
            <button
              key={i}
              aria-pressed={i === selected}
              onClick={() => setSelected(i)}
            >
              {t("common.source", { count: i + 1 })}
            </button>
          ))}
        </div>
      )}
      <h4>
        {source.document_title || source.doc_name} ·{" "}
        {source.source_location?.replace(/,\s*lines?\s*\d+-\d+/i, "")}
      </h4>
      {technical && (
        <small>
          {source.citation_id || (source.id ? `E${source.id}` : "")}
        </small>
      )}
      {pdf && page && path ? (
        <Suspense fallback={<p role="status">{t("ui.insightLoading")}</p>}>
          <SourcePdfPreview
            key={`${exam}:${path}:${page}`}
            exam={exam}
            path={path}
            page={page}
          />
        </Suspense>
      ) : (
        pdf && <p className="muted">{t("ui.insightNoPage")}</p>
      )}
      <details open={!pdf}>
        <summary>{t("ui.insightExtracted")}</summary>
        <StudyText>{source.content || source.preview}</StudyText>
      </details>
    </section>
  );
}
