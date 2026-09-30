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
          <p className="eyebrow">A little practice. A clearer answer.</p>
          <h2>Your learning dashboard</h2>
          <p className="muted">{exam.name}</p>
        </div>
        <span className="local-badge">● Private workspace</span>
      </div>
      <ErrorNotice error={error} />
      {!data || !p ? (
        <p>Loading your learning journey…</p>
      ) : (
        <>
          <div className="hero-panel">
            <div>
              <span className="eyebrow">Your next step</span>
              <h3>
                {!p.eligible_questions
                  ? "Start with a question worth exploring."
                  : !data.goal.exam_date
                    ? "Give your preparation a destination."
                    : p.overdue
                      ? "Ready for your next chapter?"
                      : p.remaining === 0
                        ? "Your practice target is complete."
                        : `${p.daily_questions} answer${p.daily_questions === 1 ? "" : "s"} today. One step closer.`}
              </h3>
              <p>
                {p.overdue
                  ? "Your exam date has passed. Update it to make a new plan."
                  : p.daily_questions
                    ? `About ${p.daily_sessions} session${p.daily_sessions === 1 ? "" : "s"} today. ${p.remaining} answers remain across ${p.study_days} days, including today and exam day.`
                    : "Set an exam date below, explore your topics, and build confidence through practice."}
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
                  ? "Start today’s practice →"
                  : "Add PDFs & prepare practice →"}
              </button>
            </div>
            <div className="hero-orbit" aria-hidden="true">
              <span>C</span>
            </div>
          </div>
          <div className="stat-grid">
            <article>
              <small>Until your exam</small>
              <strong>
                {p.days_left === null
                  ? "—"
                  : p.overdue
                    ? "Passed"
                    : `${p.days_left} days`}
              </strong>
            </article>
            <article>
              <small>Practice target</small>
              <strong>
                {p.completed}
                <em> / {p.total}</em>
              </strong>
              <progress
                value={p.completed}
                max={p.total || 1}
                aria-label="Practice target completion"
              />
            </article>
            <article>
              <small>Current streak</small>
              <strong>
                {data.streak} <em>days</em>
              </strong>
              <small>Assessed answers on consecutive days</small>
            </article>
            <article>
              <small>Answered today</small>
              <strong>{data.today_answers}</strong>
              <small>
                {
                  data.topics.filter((t) => t.mastery_state === "exam_ready")
                    .length
                }{" "}
                of {data.topics.length} topics exam ready
              </small>
            </article>
          </div>
          <div className="dashboard-columns">
            <article>
              <p className="eyebrow">Make room for learning</p>
              <h3>Your exam countdown</h3>
              <form onSubmit={save}>
                <label>
                  Exam date
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
                    Answers per question
                    <input
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
                  <label>
                    Questions per session
                    <input
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
                  {busy ? "Saving…" : "Save learning plan"}
                </button>
                {saved && (
                  <span role="status" className="success">
                    {" "}
                    Plan saved
                  </span>
                )}
              </form>
              <p className="muted">
                Each enabled, accepted question gets your chosen number of
                assessed answers. Previous answers count, up to that target per
                question. The remaining workload is spread evenly across the
                days left. This estimates practice volume, not mastery.
              </p>
            </article>
            <article>
              <p className="eyebrow">Keep showing up</p>
              <h3>Your last two weeks</h3>
              <div
                className="activity-chart"
                aria-label="Answers over the last fourteen days"
              >
                {data.activity.map((d) => (
                  <div
                    key={d.date}
                    className="activity-column"
                    title={`${d.date}: ${d.answers} assessed answers`}
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
                {data.assessed_answers} assessed answers so far. Every
                explanation is a chance to find what needs another look.
              </p>
              <button onClick={() => navigate("Progress")}>
                Explore your progress →
              </button>
            </article>
          </div>
          {!!p.schedule.length && (
            <article>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">A manageable rhythm</p>
                  <h3>Upcoming practice</h3>
                </div>
                <span className="muted">{p.remaining} answers remaining</span>
              </div>
              <div className="schedule-strip">
                {p.schedule.map((d, i) => (
                  <div key={d.date} className={i === 0 ? "today" : ""}>
                    <small>
                      {i === 0
                        ? "Today"
                        : new Date(`${d.date}T12:00:00`).toLocaleDateString(
                            undefined,
                            { month: "short", day: "numeric" },
                          )}
                    </small>
                    <strong>{d.questions}</strong>
                    <small>answers · {d.sessions} sessions</small>
                  </div>
                ))}
              </div>
              {p.study_days > 14 && (
                <p className="muted">
                  Showing the next 14 of {p.study_days} study days.
                </p>
              )}
            </article>
          )}
          <div className="page-heading">
            <div>
              <p className="eyebrow">See how it connects</p>
              <h3>Your topics</h3>
            </div>
            <button onClick={() => navigate("Questions")}>
              Open question library →
            </button>
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
