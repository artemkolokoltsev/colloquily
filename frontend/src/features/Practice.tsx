import { useEffect, useState } from "react";
import { api, operation } from "../api/client";
import {
  ErrorNotice,
  EvaluationView,
  Progress,
  Sources,
} from "../components/Common";
import type { Evaluation, Exam, Job, Run, Session } from "../types";
export function Practice({
  exams,
  selected,
  initialTopic = "",
  initialCount = 10,
}: {
  exams: Exam[];
  selected: number;
  initialTopic?: string;
  initialCount?: number;
}) {
  const [mode, setMode] = useState(
    initialTopic || initialCount > 1 ? "random_practice" : "single_question",
  );
  const [ids, setIds] = useState([selected]);
  const [run, setRun] = useState<Run>();
  const [session, setSession] = useState<Session>();
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [history, setHistory] = useState<
    { id: number; mode: string; status: string }[]
  >([]);
  const [seconds, setSeconds] = useState(60);
  const [count, setCount] = useState(initialCount);
  const [topics, setTopics] = useState(initialTopic);
  const [difficulties, setDifficulties] = useState("");
  const [priorities, setPriorities] = useState("");
  const [showTimer, setShowTimer] = useState(true);
  const [randomOrder, setRandomOrder] = useState(false);
  const splitFilter = (text: string) =>
    text
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
  const [preparation, setPreparation] = useState(0);
  const [started, setStarted] = useState(Date.now());
  useEffect(() => {
    api<typeof history>("/practice")
      .then(setHistory)
      .catch((e) => setError(String(e)));
  }, [run?.status]);
  useEffect(() => {
    if (!session) return;
    const timer = setInterval(() => {
      api<Session>(`/sessions/${session.id}`)
        .then((s) => {
          setSession(s);
          if (["completed", "time_expired"].includes(s.status) && run)
            api<Run>(`/practice/${run.id}`)
              .then(setRun)
              .catch((e) => setError(String(e)));
        })
        .catch((e) => setError(String(e)));
    }, 1000);
    return () => clearInterval(timer);
  }, [session?.id, run?.id]);
  async function act(work: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function openRun(id: number) {
    const r = await api<Run>(`/practice/${id}`);
    setRun(r);
    setSession(
      r.sessions.find(
        (s) => !["completed", "time_expired"].includes(s.status),
      ) || r.sessions.at(-1),
    );
    setAnswer("");
    setFeedback(null);
  }
  async function submit(skip = false) {
    if (!session) return;
    const result = await operation<{
      session: Session;
      evaluation: Evaluation | null;
    }>(
      `/sessions/${session.id}/${skip ? "skip" : "answer"}`,
      skip
        ? {}
        : {
            answer,
            response_duration_seconds: Math.floor(
              (Date.now() - started) / 1000,
            ),
          },
      setJob,
    );
    setSession(result.session);
    setFeedback(result.evaluation);
    setAnswer("");
    setStarted(Date.now());
    if (run) setRun(await api<Run>(`/practice/${run.id}`));
  }
  const active = session && ["answering", "preparing"].includes(session.status);
  return (
    <section>
      <p className="eyebrow">Learn by explaining</p>
      <h2>Let’s practise</h2>
      <ErrorNotice error={error} />
      {!run ? (
        <>
          <p>
            Practise{" "}
            {initialTopic ||
              exams.find((e) => e.id === selected)?.name ||
              "your exam"}{" "}
            with a short round of questions. Explain your answer, then get
            feedback grounded in your materials.
          </p>
          <details>
            <summary>Customise this session</summary>
            <label>
              Mode
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                {[
                  "single_question",
                  "rapid_practice",
                  "weak_topic",
                  "random_practice",
                  "oral_exam_simulation",
                  "subject_simulation",
                  "multi_subject",
                  "full_colloquium",
                ].map((m) => (
                  <option key={m} value={m}>
                    {m.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <fieldset>
              <legend>Choose exams (one to three)</legend>
              {exams.map((e) => (
                <label className="inline" key={e.id}>
                  <input
                    type="checkbox"
                    checked={ids.includes(e.id)}
                    onChange={(ev) =>
                      setIds(
                        ev.target.checked
                          ? [...ids, e.id]
                          : ids.filter((id) => id !== e.id),
                      )
                    }
                  />
                  {e.name}
                </label>
              ))}
            </fieldset>
            <label>
              Preparation seconds
              <input
                type="number"
                min="0"
                max="600"
                value={preparation}
                onChange={(e) => setPreparation(Number(e.target.value))}
              />
            </label>
            <label>
              Practice answer seconds
              <input
                type="number"
                min="15"
                max="3600"
                value={seconds}
                onChange={(e) => setSeconds(Number(e.target.value))}
              />
            </label>
            {["random_practice", "oral_exam_simulation"].includes(mode) && (
              <fieldset>
                <legend>Question selection</legend>
                <label>
                  Number of questions
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={count}
                    onChange={(e) => setCount(Number(e.target.value))}
                  />
                </label>
                <label>
                  Topics (comma-separated; blank for all)
                  <input
                    value={topics}
                    onChange={(e) => setTopics(e.target.value)}
                  />
                </label>
                <label>
                  Difficulties (comma-separated)
                  <input
                    value={difficulties}
                    onChange={(e) => setDifficulties(e.target.value)}
                  />
                </label>
                <label>
                  Priorities (comma-separated)
                  <input
                    value={priorities}
                    onChange={(e) => setPriorities(e.target.value)}
                  />
                </label>
              </fieldset>
            )}
            <label className="inline">
              <input
                type="checkbox"
                checked={showTimer}
                onChange={(e) => setShowTimer(e.target.checked)}
              />
              Show countdown
            </label>
            <label className="inline">
              <input
                type="checkbox"
                checked={randomOrder}
                onChange={(e) => setRandomOrder(e.target.checked)}
              />
              Randomize exam order
            </label>
          </details>
          <button
            className="primary"
            disabled={busy}
            onClick={() =>
              act(async () => {
                const r = await api<Run>("/practice", "POST", {
                  subject_ids: ids,
                  mode,
                  preparation_seconds: preparation,
                  answer_seconds: seconds,
                  question_count: count,
                  topics:
                    topics && topics === initialTopic
                      ? [initialTopic]
                      : splitFilter(topics),
                  difficulties: splitFilter(difficulties),
                  priorities: splitFilter(priorities),
                  countdown_visible: showTimer,
                  random_order: randomOrder,
                });
                setRun(r);
                setSession(r.sessions[0]);
              })
            }
          >
            Start practising
          </button>
          <h3>Previous runs</h3>
          {history.map((r) => (
            <article key={r.id}>
              <button onClick={() => act(() => openRun(r.id))}>
                Run {r.id} · {r.mode.replaceAll("_", " ")} · {r.status}
              </button>
            </article>
          ))}
        </>
      ) : (
        <>
          <div className="toolbar">
            <h3>
              Run {run.id} · {run.mode.replaceAll("_", " ")}
            </h3>
            <button
              disabled={busy}
              onClick={() => {
                setRun(undefined);
                setSession(undefined);
                setFeedback(null);
              }}
            >
              Back to runs
            </button>
          </div>
          {session && (
            <article>
              <p>
                {exams.find((e) => e.id === session.subject_id)?.name} ·{" "}
                {session.status}
                {session.countdown_visible &&
                  ` · ${Math.floor(session.remaining_seconds / 60)}:${String(session.remaining_seconds % 60).padStart(2, "0")} remaining`}
              </p>
              {["created", "queued", "transition", "preparing"].includes(
                session.status,
              ) && (
                <button
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      setSession(
                        await api<Session>(
                          `/sessions/${session.id}/begin`,
                          "POST",
                        ),
                      );
                      setStarted(Date.now());
                    })
                  }
                >
                  {session.status === "preparing"
                    ? "Begin answering"
                    : "Start this exam"}
                </button>
              )}
              {active && (
                <>
                  <h3>{session.current_question?.question_text}</h3>
                  <textarea
                    aria-label="Your oral answer"
                    placeholder="Type your answer as you would explain it aloud…"
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    disabled={busy || session.status === "preparing"}
                  />
                  <button
                    disabled={
                      busy || !answer.trim() || session.status !== "answering"
                    }
                    onClick={() => act(() => submit())}
                  >
                    Submit answer
                  </button>
                  <button
                    disabled={busy || session.status !== "answering"}
                    onClick={() => act(() => submit(true))}
                  >
                    Skip question
                  </button>
                  <Sources
                    exam={session.subject_id}
                    sources={session.sources || []}
                  />
                </>
              )}
              {["completed", "time_expired"].includes(session.status) && (
                <p>
                  This exam has finished. Review feedback below or continue to
                  the next exam.
                </p>
              )}
            </article>
          )}
          <EvaluationView value={feedback} />
          {run.sessions.map((s) => (
            <article key={s.id}>
              <strong>
                {exams.find((e) => e.id === s.subject_id)?.name} · {s.status}
              </strong>
              {["queued", "created", "transition"].includes(s.status) && (
                <button
                  disabled={busy || !!active}
                  onClick={() => {
                    setSession(s);
                    setFeedback(null);
                  }}
                >
                  Continue to this exam
                </button>
              )}
              {s.evaluation && (
                <p>
                  {s.evaluation.percent_correct}% · Grade{" "}
                  {s.evaluation.german_grade}
                </p>
              )}
              {s.attempts?.map((a) => (
                <details key={a.id}>
                  <summary>{a.question_text}</summary>
                  <p>{a.answer_text}</p>
                  <EvaluationView value={a.evaluation} />
                </details>
              ))}
            </article>
          ))}
          <button
            disabled={
              busy ||
              run.sessions.some(
                (s) => !["completed", "time_expired"].includes(s.status),
              )
            }
            onClick={() =>
              act(async () => {
                await operation(`/practice/${run.id}/evaluate`, {}, setJob);
                setRun(await api<Run>(`/practice/${run.id}`));
              })
            }
          >
            Evaluate stored answers
          </button>
          {run.overall_evaluation && (
            <p>Overall grade: {run.overall_evaluation.german_grade}</p>
          )}
        </>
      )}
      <Progress job={job} />
    </section>
  );
}
