import { useEffect, useState } from "react";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress } from "../components/Common";
import { PagedTable } from "../components/PagedTable";
import type { LearningData, Job, Question } from "../types";
export function Questions({
  exam,
  initialTopic = "",
  onPractice,
}: {
  exam: number;
  initialTopic?: string;
  onPractice: (topic: string) => void;
}) {
  const [topic, setTopic] = useState(initialTopic);
  const [learning, setLearning] = useState<LearningData>();
  const [status, setStatus] = useState("");
  const [items, setItems] = useState<Question[]>([]);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File>();
  const [preview, setPreview] = useState<unknown>();
  const [query, setQuery] = useState("");
  const refresh = () =>
    Promise.all([
      api<Question[]>(`/exams/${exam}/questions`).then(setItems),
      api<LearningData>(`/exams/${exam}/learning`).then(setLearning),
    ]);
  useEffect(() => {
    setTopic(initialTopic);
    setQuery("");
    setStatus("");
    setItems([]);
    setLearning(undefined);
    void refresh().catch((e) => setError(String(e)));
  }, [exam]);
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
  const form = () => {
    const f = new FormData();
    if (file) f.append("file", file);
    return f;
  };
  return (
    <section>
      <p className="eyebrow">Explore. Explain. Understand.</p>
      <h2>Your question library</h2>
      <p className="muted">
        Follow a topic, check your understanding, and practise explaining it
        aloud.
      </p>
      <div className="stat-grid compact-stats">
        <article>
          <span>Total questions</span>
          <strong>{items.length}</strong>
        </article>
        <article>
          <span>Available to practise</span>
          <strong>
            {learning?.topics.reduce((n, t) => n + t.available, 0) ?? "—"}
          </strong>
        </article>
        <article>
          <span>Needs review</span>
          <strong>
            {items.filter((q) => q.review_status === "needs_review").length}
          </strong>
        </article>
        <article>
          <span>Topics</span>
          <strong>
            {new Set(items.map((q) => q.topic_name || "Unassigned")).size}
          </strong>
        </article>
      </div>
      <div className="page-heading">
        <h3>{topic || "All questions"}</h3>
        <button
          className="primary"
          disabled={
            !learning?.topics.some(
              (t) => t.available > 0 && (!topic || t.name === topic),
            )
          }
          onClick={() => onPractice(topic)}
        >
          Practise {topic || "these questions"} →
        </button>
      </div>
      <ErrorNotice error={error} />
      <details>
        <summary>Manage questions · generate, import & review</summary>
        <div className="toolbar">
          <button
            disabled={busy}
            onClick={() =>
              act(() =>
                operation(
                  `/exams/${exam}/questions/generate`,
                  { count: 5 },
                  setJob,
                ),
              )
            }
          >
            Generate 5 grounded questions
          </button>
        </div>
        <details>
          <summary>Add a curated question pool</summary>
          <label>
            Import curated question pool
            <input
              type="file"
              accept=".json,.jsonl,.md,.markdown"
              onChange={(e) => {
                setFile(e.target.files?.[0]);
                setPreview(undefined);
              }}
            />
          </label>
          <button
            disabled={busy || !file}
            onClick={() =>
              act(async () =>
                setPreview(
                  await api(`/exams/${exam}/questions/preview`, "POST", form()),
                ),
              )
            }
          >
            Preview import
          </button>
          {preview !== undefined && (
            <article>
              <pre>{JSON.stringify(preview, null, 2)}</pre>
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await api(
                      `/exams/${exam}/questions/import`,
                      "POST",
                      form(),
                    );
                    setPreview(undefined);
                  })
                }
              >
                Confirm import
              </button>
            </article>
          )}
        </details>
        <Progress job={job} />
      </details>
      {!items.length && (
        <p className="empty-state">
          No practice questions yet. Open Materials, upload your PDFs, and
          choose Prepare my practice.
        </p>
      )}
      <div className="table-filters">
        <label>
          Search questions
          <input
            placeholder="Find a question…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label>
          Topic
          <select value={topic} onChange={(e) => setTopic(e.target.value)}>
            <option value="">All topics</option>
            {Array.from(new Set(items.map((q) => q.topic_name || "Unassigned")))
              .sort()
              .map((t) => (
                <option key={t}>{t}</option>
              ))}
          </select>
        </label>
        <label>
          Review status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {["accepted", "needs_review", "rejected", "quarantined"].map(
              (s) => (
                <option key={s} value={s}>
                  {s.replaceAll("_", " ")}
                </option>
              ),
            )}
          </select>
        </label>
        <button
          onClick={() => {
            setQuery("");
            setTopic("");
            setStatus("");
          }}
        >
          Clear filters
        </button>
      </div>
      <PagedTable
        label="Questions"
        resetKey={`${exam}:${query}:${topic}:${status}`}
        headers={["Question", "Topic", "Review", "Practice"]}
        rows={items.filter(
          (q) =>
            q.question_text
              .toLowerCase()
              .includes(query.trim().toLowerCase()) &&
            (!topic || (q.topic_name || "Unassigned") === topic) &&
            (!status || q.review_status === status),
        )}
        renderRow={(q) => (
          <tr key={q.id}>
            <td className="question-cell">
              <details>
                <summary>
                  <span className="row-preview">{q.question_text}</span>
                </summary>
                <div className="row-detail">
                  <p>{q.question_text}</p>
                  <h4>Expected answer points</h4>
                  {q.expected_core_points?.length ? (
                    <ul>
                      {q.expected_core_points.map((p, i) => (
                        <li key={i}>{p.text}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>No answer points yet.</p>
                  )}
                  <div className="toolbar">
                    {["accepted", "rejected", "needs_review"].map((status) => (
                      <button
                        key={status}
                        disabled={busy}
                        onClick={() =>
                          act(() =>
                            api(`/exams/${exam}/questions/${q.id}`, "PATCH", {
                              status,
                            }),
                          )
                        }
                      >
                        {status.replaceAll("_", " ")}
                      </button>
                    ))}
                  </div>
                </div>
              </details>
            </td>
            <td>{q.topic_name || "Unassigned"}</td>
            <td>
              <span className="status-label">
                {q.review_status.replaceAll("_", " ")}
              </span>
            </td>
            <td>
              <button
                disabled={busy}
                aria-label={`${q.enabled ? "Disable" : "Enable"} question ${q.id} for practice`}
                onClick={() =>
                  act(() =>
                    api(`/exams/${exam}/questions/${q.id}/enabled`, "PATCH", {
                      enabled: !q.enabled,
                    }),
                  )
                }
              >
                {q.enabled ? "Enabled" : "Disabled"}
              </button>
            </td>
          </tr>
        )}
      />
    </section>
  );
}
