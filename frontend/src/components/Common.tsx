import { useEffect, useState } from "react";
import { sourceBlob } from "../api/client";
import type { Evaluation, Job, Source } from "../types";
export function ErrorNotice({ error }: { error: string }) {
  return error ? (
    <p role="alert" className="error">
      {error}
    </p>
  ) : null;
}
export function Progress({ job }: { job: Job | null }) {
  if (!job) return null;
  return (
    <div role="status" className="progress">
      <strong>
        {job.status === "completed"
          ? "Completed · "
          : job.status === "failed"
            ? "Failed · "
            : ""}
        {job.message || job.status}
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
          {((job.completed || 0) / 1e9).toFixed(2)} /{" "}
          {(job.total / 1e9).toFixed(2)} GB
        </small>
      )}
    </div>
  );
}
export function EvaluationView({ value }: { value: Evaluation | null }) {
  if (!value) return null;
  return (
    <article>
      <h3>Answer feedback {value.score != null && `· ${value.score}/5`}</h3>
      {["correct", "missing", "incorrect"].map((key) => (
        <div key={key}>
          <h4>{key}</h4>
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
}: {
  exam: number;
  sources: Source[];
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  return (
    <div>
      <ErrorNotice error={error} />
      {sources.map((s, i) => (
        <details key={i}>
          <summary>
            {s.citation_id || (s.id ? `E${s.id}` : `Source ${i + 1}`)} ·{" "}
            {s.document_title || s.doc_name} · {s.source_location}
          </summary>
          <p className="prose">{s.content || s.preview}</p>
          {(s.relative_path || s.doc_name) && (
            <button
              onClick={() => {
                sourceBlob(exam, s.relative_path || s.doc_name!)
                  .then(setUrl)
                  .catch((e) => setError(String(e)));
              }}
            >
              Open original source
            </button>
          )}
        </details>
      ))}
      {url && (
        <div className="source-preview">
          <button onClick={() => setUrl("")}>Close source</button>
          <iframe title="Original course source" src={url} />
        </div>
      )}
    </div>
  );
}
