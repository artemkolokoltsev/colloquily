import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorNotice, EvaluationView } from "../components/Common";
import { PagedTable } from "../components/PagedTable";
import type { Evaluation, LearningData } from "../types";
interface ProgressData {
  attempts_count: number;
  average_score: number | null;
  average_response_seconds: number | null;
  topics: {
    name: string;
    mastery_state: string;
    average_score: number | null;
  }[];
  frequently_missing: [string, number][];
  misconceptions: [string, number][];
  recent_attempts: {
    id: number;
    question_text: string;
    answer_text: string;
    evaluation: Evaluation;
  }[];
}
export function ProgressPage({ exam }: { exam: number }) {
  const [learning, setLearning] = useState<LearningData>();
  const [data, setData] = useState<ProgressData>();
  const [error, setError] = useState("");
  const [tab, setTab] = useState("topics");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<number>();
  const [correction, setCorrection] = useState("");
  const refresh = () =>
    Promise.all([
      api<ProgressData>(`/exams/${exam}/progress`).then(setData),
      api<LearningData>(`/exams/${exam}/learning`).then(setLearning),
    ]);
  useEffect(() => {
    setData(undefined);
    setLearning(undefined);
    setEditing(undefined);
    setQuery("");
    void refresh().catch((e) => setError(String(e)));
  }, [exam]);
  return (
    <section>
      <h2>Learning progress</h2>
      <ErrorNotice error={error} />
      {!data ? (
        <p>Loading progress…</p>
      ) : (
        <>
          <div className="stat-grid compact-stats">
            <article>
              <span>Practice attempts</span>
              <strong>{data.attempts_count}</strong>
            </article>
            <article>
              <span>Average score</span>
              <strong>
                {data.average_score ?? "—"}
                <small> / 5</small>
              </strong>
            </article>
            <article>
              <span>Average answer</span>
              <strong>
                {data.average_response_seconds ?? "—"}
                <small> s</small>
              </strong>
            </article>
            <article>
              <span>Topics exam ready</span>
              <strong>
                {learning?.topics.filter(
                  (t) => t.mastery_state === "exam_ready",
                ).length ?? "—"}
                <small> / {learning?.topics.length ?? "—"}</small>
              </strong>
            </article>
          </div>
          <div className="toolbar" aria-label="Progress views">
            {[
              ["topics", "Topic mastery"],
              ["answers", "Recent answers"],
              ["patterns", "Learning gaps"],
            ].map(([key, label]) => (
              <button
                key={key}
                aria-pressed={tab === key}
                className={tab === key ? "active" : ""}
                onClick={() => {
                  setTab(key);
                  setQuery("");
                }}
              >
                {label}
              </button>
            ))}
          </div>
          {tab !== "patterns" && (
            <label className="table-search">
              Search {tab === "topics" ? "topics" : "answers"}
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter this view…"
              />
            </label>
          )}
          {tab === "topics" && (
            <PagedTable
              label="Topics"
              resetKey={`${exam}:${query}`}
              headers={["Topic", "Mastery", "Practised", "Score"]}
              rows={(learning?.topics ?? []).filter((t) =>
                t.name.toLowerCase().includes(query.trim().toLowerCase()),
              )}
              renderRow={(t) => (
                <tr key={t.name}>
                  <td>
                    <strong>{t.name}</strong>
                    <details>
                      <summary>Why this result?</summary>
                      <p>{t.mastery_reason}</p>
                    </details>
                  </td>
                  <td>
                    <span className="status-label">
                      {t.mastery_state.replaceAll("_", " ")}
                    </span>
                  </td>
                  <td>
                    {t.practised} / {t.questions}
                    <progress
                      aria-label={`${t.name} practice coverage`}
                      value={t.practised}
                      max={Math.max(t.questions, 1)}
                    />
                  </td>
                  <td>
                    {t.score_percent === null ? "—" : `${t.score_percent}%`}
                  </td>
                </tr>
              )}
            />
          )}
          {tab === "patterns" && (
            <>
              <h3>Frequently missing points</h3>
              <PagedTable
                label="Missing points"
                rows={data.frequently_missing}
                headers={["Point to revisit", "Occurrences"]}
                renderRow={([s, n]) => (
                  <tr key={s}>
                    <td>{s}</td>
                    <td>{n}</td>
                  </tr>
                )}
              />
              <h3>Misconceptions</h3>
              <PagedTable
                label="Misconceptions"
                rows={data.misconceptions}
                headers={["Misconception", "Occurrences"]}
                renderRow={([s, n]) => (
                  <tr key={s}>
                    <td>{s}</td>
                    <td>{n}</td>
                  </tr>
                )}
              />
            </>
          )}
          {tab === "answers" && (
            <PagedTable
              label="Recent answers"
              resetKey={`${exam}:${query}`}
              headers={["Question & feedback", "Score"]}
              rows={data.recent_attempts.filter((a) =>
                a.question_text
                  .toLowerCase()
                  .includes(query.trim().toLowerCase()),
              )}
              renderRow={(a) => (
                <tr key={a.id}>
                  <td className="question-cell">
                    <details key={a.id}>
                      <summary>
                        <span className="row-preview">{a.question_text}</span>
                      </summary>
                      <p>{a.question_text}</p>
                      <p>{a.answer_text}</p>
                      <EvaluationView value={a.evaluation} />
                      <button
                        onClick={() => {
                          setEditing(a.id);
                          setCorrection(JSON.stringify(a.evaluation, null, 2));
                        }}
                      >
                        Correct evaluation
                      </button>
                      {editing === a.id && (
                        <>
                          <label>
                            Evaluation JSON
                            <textarea
                              value={correction}
                              onChange={(e) => setCorrection(e.target.value)}
                            />
                          </label>
                          <button
                            onClick={async () => {
                              setError("");
                              try {
                                await api(
                                  `/exams/${exam}/attempts/${a.id}`,
                                  "PATCH",
                                  {
                                    evaluation: JSON.parse(correction),
                                  },
                                );
                                setEditing(undefined);
                                await refresh();
                              } catch (e) {
                                setError(String(e));
                              }
                            }}
                          >
                            Save correction
                          </button>
                        </>
                      )}
                    </details>
                  </td>
                  <td>{a.evaluation?.score ?? "—"} / 5</td>
                </tr>
              )}
            />
          )}
        </>
      )}
    </section>
  );
}
