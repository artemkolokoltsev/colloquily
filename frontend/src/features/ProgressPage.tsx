import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorNotice, EvaluationView } from "../components/Common";
import { PagedTable } from "../components/PagedTable";
import type { Evaluation, LearningData } from "../types";
interface ProgressData {
  attempts_count: number;
  evaluated_count: number;
  skipped_count: number;
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
  const { t: tr } = useTranslation();
  const [learning, setLearning] = useState<LearningData>();
  const [data, setData] = useState<ProgressData>();
  const [older, setOlder] = useState<ProgressData["recent_attempts"]>([]);
  const [more, setMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("topics");
  const [query, setQuery] = useState("");
  const refresh = () =>
    Promise.all([
      api<ProgressData>(`/exams/${exam}/progress`).then(setData),
      api<LearningData>(`/exams/${exam}/learning`).then(setLearning),
    ]);
  useEffect(() => {
    setData(undefined);
    setLearning(undefined);
    setQuery("");
    void refresh().catch((e) => setError(String(e)));
  }, [exam]);
  return (
    <section>
      <h2>{tr("ui.s839de264eb")}</h2>
      <ErrorNotice error={error} />
      {!data ? (
        <p>{tr("ui.s7e34513f0c")}</p>
      ) : (
        <>
          <div className="stat-grid compact-stats">
            <article>
              <span>{tr("ui.s1e636982e8")}</span>
              <strong>{data.attempts_count}</strong>
            </article>
            <article>
              <span>{tr("ui.se4870be722")}</span>
              <strong>
                {data.average_score ?? "—"}
                <small> / 5</small>
              </strong>
            </article>
            <article>
              <span>{tr("ui.s0cfb6b5382")}</span>
              <strong>
                {data.average_response_seconds ?? "—"}
                <small> {tr("ui.s043a718774")}</small>
              </strong>
            </article>
            <article>
              <span>{tr("ui.s659b6f396d")}</span>
              <strong>
                {learning?.topics.filter(
                  (t) => t.mastery_state === "exam_ready",
                ).length ?? "—"}
                <small> / {learning?.topics.length ?? "—"}</small>
              </strong>
            </article>
          </div>
          <div className="toolbar" aria-label={tr("ui.sb9cf9b8b98")}>
            {[
              ["topics", "ui.topicMastery"],
              ["answers", "ui.recentAnswers"],
              ["patterns", "ui.learningGaps"],
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
                {tr(label as "ui.topicMastery")}
              </button>
            ))}
          </div>
          {tab !== "patterns" && (
            <label className="table-search">
              {" "}
              {tr("ui.s49c266baaa")}{" "}
              {tab === "topics" ? tr("ui.sf013aa4b8d") : tr("ui.s677fe21b65")}
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={tr("ui.s26634f572c")}
              />
            </label>
          )}
          {tab === "topics" && (
            <PagedTable
              label={tr("ui.se22820fcf5")}
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
                      <summary>{tr("ui.s23e4ca427c")}</summary>
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
              <h3>{tr("ui.s1b5db84e99")}</h3>
              <PagedTable
                label={tr("ui.sb910ef4678")}
                rows={data.frequently_missing}
                headers={["Point to revisit", "Occurrences"]}
                renderRow={([s, n]) => (
                  <tr key={s}>
                    <td>{s}</td>
                    <td>{n}</td>
                  </tr>
                )}
              />
              <h3>{tr("ui.sd3e410d6fc")}</h3>
              <PagedTable
                label={tr("ui.sd3e410d6fc")}
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
            <div className="answer-history">
              <p>
                {tr("ui.attemptCounts", {
                  evaluated: data.evaluated_count,
                  skipped: data.skipped_count,
                })}
              </p>
              <div className="score-trend" aria-label={tr("ui.scoreTrend")}>
                {[...data.recent_attempts]
                  .reverse()
                  .filter(
                    (a) =>
                      a.evaluation?.score != null &&
                      a.evaluation.status !== "skipped",
                  )
                  .map((a) => (
                    <span key={a.id} title={a.question_text}>
                      {a.evaluation.score}/5
                    </span>
                  ))}
              </div>
              {[...data.recent_attempts, ...older]
                .filter((a) =>
                  a.question_text
                    .toLowerCase()
                    .includes(query.trim().toLowerCase()),
                )
                .map((a) => (
                  <article key={a.id}>
                    <details>
                      <summary>
                        <strong>{a.question_text}</strong> ·{" "}
                        {a.evaluation?.status === "skipped"
                          ? 0
                          : (a.evaluation?.score ?? "—")}
                        /5 ·{" "}
                        {a.evaluation?.status === "skipped"
                          ? tr("ui.skipped")
                          : tr("ui.evaluated")}
                      </summary>
                      {a.answer_text && (
                        <>
                          <h4>{tr("ui.yourAnswer")}</h4>
                          <p className="prose">{a.answer_text}</p>
                        </>
                      )}
                      <EvaluationView value={a.evaluation} />
                    </details>
                  </article>
                ))}
              {more && data.recent_attempts.length >= 20 && (
                <button
                  disabled={loadingMore}
                  onClick={async () => {
                    setLoadingMore(true);
                    try {
                      const items = [...data.recent_attempts, ...older];
                      const result = await api<{
                        items: ProgressData["recent_attempts"];
                        has_more: boolean;
                      }>(
                        `/exams/${exam}/attempts?before=${Math.min(...items.map((item) => item.id))}`,
                      );
                      setOlder((previous) => [...previous, ...result.items]);
                      setMore(result.has_more);
                    } catch (e) {
                      setError(String(e));
                    } finally {
                      setLoadingMore(false);
                    }
                  }}
                >
                  {tr("ui.olderAnswers")}
                </button>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
