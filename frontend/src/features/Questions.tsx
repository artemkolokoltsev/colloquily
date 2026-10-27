import { StudyText } from "../components/StudyText";
import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress, Sources } from "../components/Common";
import { PagedTable } from "../components/PagedTable";
import type { LearningData, Job, Question, Source } from "../types";
export function Questions({
  exam,
  initialTopic = "",
  onPractice,
}: {
  exam: number;
  initialTopic?: string;
  onPractice: (topic: string) => void;
}) {
  const { t } = useTranslation();
  const [topics, setTopics] = useState<{ id: number; name: string }[]>([]);
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
      api<{ id: number; name: string }[]>(`/exams/${exam}/topics`).then(
        setTopics,
      ),
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
      <p className="eyebrow">{t("ui.s2907aaf86b")}</p>
      <h2>{t("ui.s83ed79c22e")}</h2>
      <p className="muted"> {t("ui.s5a40fc78c4")} </p>
      <div className="stat-grid compact-stats">
        <article>
          <span>{t("ui.scafd3bd241")}</span>
          <strong>{items.length}</strong>
        </article>
        <article>
          <span>{t("ui.scbf0dfe6ba")}</span>
          <strong>
            {learning?.topics.reduce((n, t) => n + t.available, 0) ?? "—"}
          </strong>
        </article>
        <article>
          <span>{t("ui.s07297fa94a")}</span>
          <strong>
            {items.filter((q) => q.review_status === "needs_review").length}
          </strong>
        </article>
        <article>
          <span>{t("ui.se22820fcf5")}</span>
          <strong>
            {new Set(items.map((q) => q.topic_name || "Unassigned")).size}
          </strong>
        </article>
      </div>
      <div className="page-heading">
        <h3>{topic || t("ui.s5314becbd6")}</h3>
        <button
          className="primary"
          disabled={
            !learning?.topics.some(
              (t) => t.available > 0 && (!topic || t.name === topic),
            )
          }
          onClick={() => onPractice(topic)}
        >
          {" "}
          {t("ui.scb93da9e26")} {topic || t("ui.see6ba3f561")} →
        </button>
      </div>
      <ErrorNotice error={error} />
      <button
        disabled={busy}
        onClick={() =>
          void act(() => operation(`/exams/${exam}/prepare`, {}, setJob))
        }
      >
        {t("ui.redesignFillCoverage")}
      </button>
      <Progress job={job} />
      <details>
        <summary>{t("ui.s465e030650")}</summary>
        <button
          disabled={busy}
          onClick={() =>
            void act(() =>
              operation(`/exams/${exam}/questions/reclassify`, {}, setJob),
            )
          }
        >
          {t("ui.reclassify")}
        </button>
        {job?.status === "completed" && !!job.result && (
          <pre>{JSON.stringify(job.result, null, 2)}</pre>
        )}
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
            {" "}
            {t("ui.sfe13549010")}{" "}
          </button>
        </div>
        <details>
          <summary>{t("ui.s422b432c52")}</summary>
          <label>
            {" "}
            {t("ui.sc989cc910d")}{" "}
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
            {" "}
            {t("ui.sab5c8e55ce")}{" "}
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
                {" "}
                {t("ui.s4ca48b4230")}{" "}
              </button>
            </article>
          )}
        </details>
        <Progress job={job} />
      </details>
      {!items.length && <p className="empty-state"> {t("ui.sfd6d154a98")} </p>}
      <div className="table-filters">
        <label>
          {" "}
          {t("ui.s7fa8a1cfca")}{" "}
          <input
            placeholder={t("ui.s4f2ac56036")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label>
          {" "}
          {t("ui.s7e61847d61")}{" "}
          <select value={topic} onChange={(e) => setTopic(e.target.value)}>
            <option value="">{t("ui.s29366ff597")}</option>
            {Array.from(new Set(items.map((q) => q.topic_name || "Unassigned")))
              .sort()
              .map((t) => (
                <option key={t}>{t}</option>
              ))}
          </select>
        </label>
        <label>
          {" "}
          {t("ui.sa410d70156")}{" "}
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">{t("ui.s8ee57323a6")}</option>
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
          {" "}
          {t("ui.s7179ea0035")}{" "}
        </button>
      </div>
      <PagedTable
        label={t("ui.s9a72221a27")}
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
                  <StudyText>{q.question_text}</StudyText>
                  <h4>{t("ui.s6d139c6975")}</h4>
                  {q.expected_core_points?.length ? (
                    <ul>
                      {q.expected_core_points.map((p, i) => (
                        <li key={i}>{p.text}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>{t("ui.sc67fe62b5d")}</p>
                  )}
                  <QuestionCitations exam={exam} question={q.id} />
                  <label>
                    {t("ui.topicAssignment")}
                    <select
                      value={
                        topics.find((topic) => topic.name === q.topic_name)
                          ?.id ?? ""
                      }
                      disabled={busy}
                      onChange={(e) =>
                        void act(() =>
                          api(
                            `/exams/${exam}/questions/${q.id}/topic`,
                            "PATCH",
                            {
                              topic_id: e.target.value
                                ? Number(e.target.value)
                                : null,
                            },
                          ),
                        )
                      }
                    >
                      <option value="">{t("ui.s14d33bd014")}</option>
                      {topics.map((topic) => (
                        <option key={topic.id} value={topic.id}>
                          {topic.name}
                        </option>
                      ))}
                    </select>
                  </label>
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
                        {t(`dynamic.${status}`, {
                          defaultValue: status.replaceAll("_", " "),
                        })}
                      </button>
                    ))}
                  </div>
                </div>
              </details>
            </td>
            <td>{q.topic_name || t("ui.s14d33bd014")}</td>
            <td>
              <span className="status-label">
                {t(`dynamic.${q.review_status}`, {
                  defaultValue: q.review_status.replaceAll("_", " "),
                })}
              </span>
            </td>
            <td>
              <button
                disabled={busy}
                aria-label={t("dynamic.questionToggle", {
                  action: t(q.enabled ? "dynamic.disable" : "dynamic.enable"),
                  id: q.id,
                })}
                onClick={() =>
                  act(() =>
                    api(`/exams/${exam}/questions/${q.id}/enabled`, "PATCH", {
                      enabled: !q.enabled,
                    }),
                  )
                }
              >
                {q.enabled ? t("ui.s92c1cdfdf4") : t("ui.s75081b593d")}
              </button>
            </td>
          </tr>
        )}
      />
    </section>
  );
}

function QuestionCitations({
  exam,
  question,
}: {
  exam: number;
  question: number;
}) {
  const { t } = useTranslation();
  const [sources, setSources] = useState<Source[]>();
  const [error, setError] = useState("");
  return (
    <details
      onToggle={(event) => {
        if (event.currentTarget.open && !sources)
          void api<Source[]>(`/exams/${exam}/questions/${question}/sources`)
            .then(setSources)
            .catch((e) => setError(String(e)));
      }}
    >
      <summary>{t("ui.questionSources")}</summary>
      <ErrorNotice error={error} />
      {sources && <Sources exam={exam} sources={sources} />}
      {sources?.length === 0 && <p>{t("ui.noLectureSources")}</p>}
    </details>
  );
}
