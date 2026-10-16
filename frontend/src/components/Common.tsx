import { useEffect, useState } from "react";
import { sourceBlob } from "../api/client";
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
          max={job.status === "completed" ? 100 : job.total || undefined}
          value={
            job.status === "completed"
              ? 100
              : job.total
                ? job.completed
                : undefined
          }
        />
      )}
      {!!job.total && (
        <small>
          {Math.round(((job.completed || 0) / job.total) * 100)}% ·{" "}
          {job.total > 1000000
            ? `${((job.completed || 0) / 1e9).toFixed(2)} / ${(job.total / 1e9).toFixed(2)} GB`
            : `${job.completed || 0} / ${job.total}`}
        </small>
      )}
    </div>
  );
}
export function EvaluationView({ value }: { value: Evaluation | null }) {
  const { t } = useTranslation();
  if (!value) return null;
  return (
    <article>
      <h3>
        {t("common.answerFeedback")}{" "}
        {value.score != null && `· ${value.score}/5`}
      </h3>
      {(["correct", "missing", "incorrect"] as const).map((key) => (
        <div key={key}>
          <h4>{t(`common.${key}`)}</h4>
          <ul>
            {(value[key as "correct"] || []).map((item, i) => (
              <li key={i}>{item.text || item.claim || JSON.stringify(item)}</li>
            ))}
          </ul>
        </div>
      ))}
      <p className="prose">{value.better_oral_answer}</p>
      {value.subject_id && (
        <Sources exam={value.subject_id} sources={value.sources || []} />
      )}
    </article>
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
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url.split("#")[0]);
    },
    [url],
  );
  return (
    <div>
      <ErrorNotice error={error} />
      {sources.map((s, i) => (
        <details key={i}>
          <summary>
            {technical
              ? s.citation_id ||
                (s.id ? `E${s.id}` : t("common.source", { count: i + 1 }))
              : t("common.source", { count: i + 1 })}{" "}
            · {s.document_title || s.doc_name} ·{" "}
            {technical
              ? s.source_location
              : s.source_location?.replace(/,\s*lines?\s*\d+-\d+/i, "")}
          </summary>
          <p className="prose">{s.content || s.preview}</p>
          {(s.relative_path || s.doc_name) && (
            <button
              onClick={() => {
                sourceBlob(exam, s.relative_path || s.doc_name!)
                  .then((blobUrl) => {
                    const page = sourcePage(s);
                    setUrl(page ? `${blobUrl}#page=${page}` : blobUrl);
                  })
                  .catch((e) => setError(String(e)));
              }}
            >
              {t("common.openSource")}
            </button>
          )}
        </details>
      ))}
      {url && (
        <div className="source-preview">
          <button onClick={() => setUrl("")}>{t("common.closeSource")}</button>
          <iframe title="Original course source" src={url} />
        </div>
      )}
    </div>
  );
}
