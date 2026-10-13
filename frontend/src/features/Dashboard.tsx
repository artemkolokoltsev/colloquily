import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorNotice } from "../components/Common";
import { LearningMap } from "../components/LearningMap";
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
    api<LearningData>(`/exams/${exam.id}/learning`)
      .then((d) => {
        setData(d);
        setGoal(d.goal);
      })
      .catch((e) => setError(String(e)));
  }, [exam.id]);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const d = await api<LearningData>(
        `/exams/${exam.id}/learning-goal`,
        "PUT",
        goal,
      );
      setData(d);
      setSaved(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const p = data?.plan;
  return (
    <section className="dashboard">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t('ui.s477b55a438')}</p>
          <h2>{t('ui.s63e208aef0')}</h2>
          <p className="muted">{exam.name}</p>
        </div>
        <span className="local-badge">{t('ui.sa234b6fcea')}</span>
      </div>
      <ErrorNotice error={error} />
      {!data || !p ? (
        <p>{t('ui.s59c125724a')}</p>
      ) : (
        <>
          <div className="hero-panel">
            <div>
              <span className="eyebrow">{t('ui.sd6c92918d6')}</span>
              <h3>
                {!p.eligible_questions
                  ? t('ui.s40ad0466c6')
                  : !data.goal.exam_date
                    ? t('ui.s56e617c552')
                    : p.overdue
                      ? t('ui.sd93f6263de')
                      : p.remaining === 0
                        ? t('ui.sdc848e7a26')
                        : t('dynamic.daily', { count: p.daily_questions })}
              </h3>
              <p>
                {p.overdue
                  ? t('ui.sb301b73b63')
                  : p.daily_questions
                    ? t('dynamic.workload', { sessions: p.daily_sessions, answers: p.remaining, days: p.study_days })
                    : t('ui.s74838d2bb7')}
              </p>
              <button
                className="primary"
                onClick={() =>
                  navigate(
                    p.eligible_questions ? "Practice" : "Materials",
                    "",
                    Math.min(
                      data.goal.questions_per_session,
                      p.daily_questions || data.goal.questions_per_session,
                    ),
                  )
                }
              >
                {p.eligible_questions
                  ? t('ui.sff50ea771f')
                  : t('ui.s2c1f04278e')}
              </button>
            </div>
            <div className="hero-orbit" aria-hidden="true">
              <span>{t('ui.s6b23c0d5f3')}</span>
            </div>
          </div>
          <div className="stat-grid">
            <article>
              <small>{t('ui.s3bf9a717cf')}</small>
              <strong>
                {p.days_left === null
                  ? "—"
                  : p.overdue
                    ? t('ui.s436fe71bb9')
                    : t('dynamic.days', { count: p.days_left })}
              </strong>
            </article>
            <article>
              <small>{t('ui.sf40a7617c9')}</small>
              <strong>
                {p.completed}
                <em> / {p.total}</em>
              </strong>
              <progress
                value={p.completed}
                max={p.total || 1}
                aria-label={t('ui.sd3f0292690')}
              />
            </article>
            <article>
              <small>{t('ui.sf1758c2815')}</small>
              <strong>
                {data.streak} <em>{t('ui.sab51004e9d')}</em>
              </strong>
              <small>{t('ui.s517c158703')}</small>
            </article>
            <article>
              <small>{t('ui.sc7bd532335')}</small>
              <strong>{data.today_answers}</strong>
              <small>
                {
                  data.topics.filter((t) => t.mastery_state === "exam_ready")
                    .length
                }{" "} {t('ui.s28391d3bc6')} {data.topics.length} {t('ui.s7fa89947ae')} </small>
            </article>
          </div>
          <div className="dashboard-columns">
            <article>
              <p className="eyebrow">{t('ui.s0fc9c48c17')}</p>
              <h3>{t('ui.s477cb6f776')}</h3>
              <form onSubmit={save}>
                <label> {t('ui.s03cff67c1b')} <input
                    type="date"
                    value={goal.exam_date || ""}
                    onChange={(e) => {
                      setGoal({ ...goal, exam_date: e.target.value || null });
                      setSaved(false);
                    }}
                  />
                </label>
                <div className="field-row">
                  <label> {t('ui.s68867baa1a')} <input
                      type="number"
                      min="1"
                      max="10"
                      required
                      value={goal.repetitions}
                      onChange={(e) =>
                        setGoal({
                          ...goal,
                          repetitions: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                  <label> {t('ui.s06d46679e7')} <input
                      type="number"
                      min="1"
                      max="100"
                      required
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
                <button className="primary" disabled={busy}>
                  {busy ? t('ui.s23e39291d6') : t('ui.s3ec6d4a587')}
                </button>
                {saved && (
                  <span role="status" className="success">
                    {" "} {t('ui.sbf83b12675')} </span>
                )}
              </form>
              <p className="muted"> {t('ui.se56daba219')} </p>
            </article>
            <article>
              <p className="eyebrow">{t('ui.s7a6a196366')}</p>
              <h3>{t('ui.s1dd706cd4e')}</h3>
              <div
                className="activity-chart"
                aria-label={t('ui.sf7ba3dd51f')}
              >
                {data.activity.map((d) => (
                  <div
                    key={d.date}
                    className="activity-column"
                    title={t('dynamic.activity', { date: d.date, count: d.answers })}
                  >
                    <span>{d.answers || ""}</span>
                    <div
                      style={{
                        height: `${Math.max(4, (d.answers / Math.max(1, ...data.activity.map((a) => a.answers))) * 95)}px`,
                      }}
                    />
                    <small>{Number(d.date.slice(-2))}</small>
                  </div>
                ))}
              </div>
              <p>
                {data.assessed_answers} {t('ui.sac66b1edc3')} </p>
              <button onClick={() => navigate("Progress")}> {t('ui.s76990f53ea')} </button>
            </article>
          </div>
          {!!p.schedule.length && (
            <article>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">{t('ui.sce6a6d8912')}</p>
                  <h3>{t('ui.s8c2497667e')}</h3>
                </div>
                <span className="muted">{p.remaining} {t('ui.s1c1e0be859')}</span>
              </div>
              <div className="schedule-strip">
                {p.schedule.map((d, i) => (
                  <div key={d.date} className={i === 0 ? 'today' : ""}>
                    <small>
                      {i === 0
                        ? t('ui.s2b065c7c9c')
                        : new Date(`${d.date}T12:00:00`).toLocaleDateString(
                            i18n.resolvedLanguage,
                            { month: "short", day: "numeric" },
                          )}
                    </small>
                    <strong>{d.questions}</strong>
                    <small>{t('ui.sc4e722d09e')} {d.sessions} {t('ui.s1225ae6c1a')}</small>
                  </div>
                ))}
              </div>
              {p.study_days > 14 && (
                <p className="muted"> {t('ui.sa245b95954')} {p.study_days} {t('ui.s9bcabfec1a')} </p>
              )}
            </article>
          )}
          <div className="page-heading">
            <div>
              <p className="eyebrow">{t('ui.sfb9d3345ae')}</p>
              <h3>{t('ui.s04f8dad9e7')}</h3>
            </div>
            <button onClick={() => navigate("Questions")}> {t('ui.sd70e316799')} </button>
          </div>
          <LearningMap
            topics={data.topics}
            selected=""
            onSelect={(topic) => navigate("Questions", topic)}
          />
        </>
      )}
    </section>
  );
}
