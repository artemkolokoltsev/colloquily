import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorNotice } from "../components/Common";
import type { Exam, LearningData } from "../types";
export function Dashboard({
  exam,
  navigate,
}: {
  exam: Exam;
  navigate: (page: string, topic?: string, count?: number) => void;
}) {
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<LearningData>();
  const [goal, setGoal] = useState<LearningData["goal"]>({
    exam_date: null,
    repetitions: 3,
    questions_per_session: 10,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    let active = true;
    setData(undefined);
    void api<LearningData>(`/exams/${exam.id}/learning`)
      .then((d) => {
        if (active) {
          setData(d);
          setGoal(d.goal);
        }
      })
      .catch((e) => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, [exam.id]);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      setData(
        await api<LearningData>(`/exams/${exam.id}/learning-goal`, "PUT", goal),
      );
      setSaved(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const p = data?.plan;
  return (
    <section
      className="dashboard"
      data-update-blocked={
        !data || busy || JSON.stringify(goal) !== JSON.stringify(data.goal)
      }
    >
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t("nav.dashboard")}</p>
          <h2>{exam.name}</h2>
        </div>
        <button onClick={() => navigate("Progress")}>
          {t("ui.s76990f53ea")}
        </button>
      </div>
      <ErrorNotice error={error} />
      {!data || !p ? (
        <p role="status">{t("ui.s59c125724a")}</p>
      ) : (
        <>
          <div className="hero-panel">
            <div>
              <p className="eyebrow">{t("ui.todayGoal")}</p>
              <h3>
                {!p.eligible_questions
                  ? t("ui.s40ad0466c6")
                  : p.overdue
                    ? t("ui.sd93f6263de")
                    : data.today_completed >= data.today_target
                      ? t("ui.sdc848e7a26")
                      : t("ui.dailyTarget", {
                          count: Math.max(
                            0,
                            data.today_target - data.today_completed,
                          ),
                        })}
              </h3>
              <p>
                {p.overdue
                  ? t("ui.sb301b73b63")
                  : t("ui.todayCompletion", {
                      count: data.today_completed,
                      total: data.today_target,
                    })}
              </p>
              <button
                className="primary"
                onClick={() =>
                  navigate(
                    p.eligible_questions ? "Practice" : "Materials",
                    "",
                    Math.min(
                      goal.questions_per_session,
                      p.daily_questions || goal.questions_per_session,
                    ),
                  )
                }
              >
                {p.eligible_questions
                  ? t("ui.sff50ea771f")
                  : t("ui.s2c1f04278e")}
              </button>
            </div>
          </div>
          <div className="stat-grid">
            <article>
              <small>{t("ui.s3bf9a717cf")}</small>
              <strong>
                {p.days_left === null
                  ? "—"
                  : p.overdue
                    ? t("ui.s436fe71bb9")
                    : t("dynamic.days", { count: p.days_left })}
              </strong>
            </article>
            <article>
              <small>{t("ui.questionsPracticed")}</small>
              <strong>
                {data.practised_questions}
                <em> / {p.eligible_questions}</em>
              </strong>
              <progress
                value={data.practised_questions}
                max={p.eligible_questions || 1}
                aria-label={t("ui.questionsPracticed")}
              />
            </article>
            <article>
              <small>{t("ui.averageEvaluated")}</small>
              <strong>
                {data.average_score ?? "—"}
                <em> / 5</em>
              </strong>
              <small>{t("ui.evaluatedOnly")}</small>
            </article>
            <article>
              <small>{t("ui.sf1758c2815")}</small>
              <strong>
                {data.streak}
                <em> {t("ui.sab51004e9d")}</em>
              </strong>
            </article>
          </div>
          <article>
            <h3>{t("ui.s1dd706cd4e")}</h3>
            <div className="activity-chart" aria-label={t("ui.sf7ba3dd51f")}>
              {data.activity.map((d) => (
                <div
                  className="activity-column"
                  key={d.date}
                  title={t("dynamic.activity", {
                    date: d.date,
                    count: d.answers,
                  })}
                >
                  <span>{d.answers || ""}</span>
                  <div
                    style={{
                      height: `${Math.max(4, (d.answers / Math.max(1, ...data.activity.map((a) => a.answers))) * 80)}px`,
                    }}
                  />
                  <small>
                    {new Date(`${d.date}T12:00:00`).toLocaleDateString(
                      i18n.resolvedLanguage,
                      { day: "numeric", month: "short" },
                    )}
                  </small>
                </div>
              ))}
            </div>
          </article>
          <article>
            <details>
              <summary>{t("ui.editPlan")}</summary>
              <form onSubmit={save}>
                <label>
                  {t("exam.date")}
                  <input
                    type="date"
                    value={goal.exam_date || ""}
                    onChange={(e) => {
                      setGoal({ ...goal, exam_date: e.target.value || null });
                      setSaved(false);
                    }}
                  />
                </label>
                <div className="field-row">
                  <label>
                    {t("ui.s68867baa1a")}
                    <input
                      type="number"
                      required
                      min={1}
                      max={10}
                      value={goal.repetitions}
                      onChange={(e) =>
                        setGoal({
                          ...goal,
                          repetitions: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                  <label>
                    {t("ui.s06d46679e7")}
                    <input
                      type="number"
                      required
                      min={1}
                      max={100}
                      value={goal.questions_per_session}
                      onChange={(e) =>
                        setGoal({
                          ...goal,
                          questions_per_session: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                </div>
                <button disabled={busy}>{t("ui.s3ec6d4a587")}</button>
                {saved && <span role="status">{t("ui.sbf83b12675")}</span>}
              </form>
              <p>
                {t("ui.repetitionProgress", {
                  count: p.completed,
                  total: p.total,
                })}
              </p>
              {!!p.schedule.length && (
                <div className="schedule-strip">
                  {p.schedule.map((d) => (
                    <div key={d.date}>
                      <small>
                        {new Date(`${d.date}T12:00:00`).toLocaleDateString(
                          i18n.resolvedLanguage,
                          { weekday: "short", month: "short", day: "numeric" },
                        )}
                      </small>
                      <strong>{d.questions}</strong>
                      <small>
                        {t("ui.sc4e722d09e")} {d.sessions}
                      </small>
                    </div>
                  ))}
                </div>
              )}
              {p.study_days > 14 && (
                <p>
                  {t("ui.sa245b95954")} {p.study_days} {t("ui.s9bcabfec1a")}
                </p>
              )}
            </details>
          </article>
          <div className="page-heading">
            <h3>{t("ui.weakTopics")}</h3>
            <button onClick={() => navigate("Questions")}>
              {t("ui.manageQuestions")}
            </button>
          </div>
          <p className="muted">{t("ui.masteryCaution")}</p>
          <div className="topic-overview">
            {[...data.topics]
              .sort((a, b) => (a.score_percent ?? -1) - (b.score_percent ?? -1))
              .map((topic) => (
                <article key={topic.name}>
                  <h4>
                    {topic.name === "Unassigned"
                      ? t("ui.s14d33bd014")
                      : topic.name}
                  </h4>
                  <p>
                    {t("ui.practisedAvailable", {
                      count: topic.practised,
                      total: topic.questions,
                    })}{" "}
                    ·{" "}
                    {topic.score_percent === null
                      ? t("ui.notPractised")
                      : `${topic.score_percent}%`}
                  </p>
                  <details>
                    <summary>{t("ui.details")}</summary>
                    <p>{topic.mastery_reason}</p>
                  </details>
                  <button
                    disabled={!topic.available}
                    onClick={() => navigate("Practice", topic.name)}
                  >
                    {t("nav.practice")}
                  </button>
                </article>
              ))}
          </div>
        </>
      )}
    </section>
  );
}
