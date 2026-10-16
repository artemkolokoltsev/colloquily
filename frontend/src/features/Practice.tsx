import { useTranslation } from "react-i18next";
import { useEffect, useRef, useState } from "react";
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
  const { t } = useTranslation();
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
  const submitting = useRef(false);
  const transitionVersion = useRef(0);
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
    api<typeof history>(`/practice?subject_id=${selected}`)
      .then(setHistory)
      .catch((e) => setError(String(e)));
  }, [run?.status, selected]);
  useEffect(() => {
    if (!session) return;
    const timer = setInterval(() => {
      if (submitting.current) return;
      const version = transitionVersion.current;
      api<Session>(`/sessions/${session.id}`)
        .then((s) => {
          if (version !== transitionVersion.current || submitting.current)
            return;
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
    if (!session || submitting.current) return;
    submitting.current = true;
    transitionVersion.current += 1;
    setJob(null);
    setFeedback(null);
    try {
      const result = skip
        ? await api<{ session: Session; evaluation: null }>(
            `/sessions/${session.id}/skip`,
            "POST",
            { question_id: session.current_question?.id },
          )
        : await operation<{
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
    } finally {
      submitting.current = false;
    }
  }
  const active = session && ["answering", "preparing"].includes(session.status);
  return (
    <section>
      <p className="eyebrow">{t("ui.s065983d64c")}</p>
      <h2>{t("ui.sc85302325b")}</h2>
      <ErrorNotice error={error} />
      {!run ? (
        <>
          <p>
            {" "}
            {t("ui.scb93da9e26")}{" "}
            {initialTopic ||
              exams.find((e) => e.id === selected)?.name ||
              t("ui.s76732acc88")}{" "}
            {t("ui.sab261a436a")}{" "}
          </p>
          <details>
            <summary>{t("ui.sef46ed5421")}</summary>
            <label>
              {" "}
              {t("ui.s5e23ec6a30")}{" "}
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
                    {t(`dynamic.${m}`, {
                      defaultValue: m.replaceAll("_", " "),
                    })}
                  </option>
                ))}
              </select>
            </label>
            <fieldset>
              <legend>{t("ui.s16aaf28e05")}</legend>
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
              {" "}
              {t("ui.s2762dc6987")}{" "}
              <input
                type="number"
                min="0"
                max="600"
                value={preparation}
                onChange={(e) => setPreparation(Number(e.target.value))}
              />
            </label>
            <label>
              {" "}
              {t("ui.sb14a6e6b6a")}{" "}
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
                <legend>{t("ui.sdfe98ae2f8")}</legend>
                <label>
                  {" "}
                  {t("ui.s4bbde39fcd")}{" "}
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={count}
                    onChange={(e) => setCount(Number(e.target.value))}
                  />
                </label>
                <label>
                  {" "}
                  {t("ui.sd512c2854e")}{" "}
                  <input
                    value={topics}
                    onChange={(e) => setTopics(e.target.value)}
                  />
                </label>
                <label>
                  {" "}
                  {t("ui.s00513010d0")}{" "}
                  <input
                    value={difficulties}
                    onChange={(e) => setDifficulties(e.target.value)}
                  />
                </label>
                <label>
                  {" "}
                  {t("ui.s3972666299")}{" "}
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
              />{" "}
              {t("ui.s7af619382c")}{" "}
            </label>
            <label className="inline">
              <input
                type="checkbox"
                checked={randomOrder}
                onChange={(e) => setRandomOrder(e.target.checked)}
              />{" "}
              {t("ui.s6eab5bfe15")}{" "}
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
            {" "}
            {t("ui.s4954d147d3")}{" "}
          </button>
          <h3>{t("ui.sf871f70262")}</h3>
          {history.map((r) => (
            <article key={r.id}>
              <button onClick={() => act(() => openRun(r.id))}>
                {" "}
                {t("ui.s00d60e31a4")} {r.id} · {r.mode.replaceAll("_", " ")} ·{" "}
                {r.status}
              </button>
            </article>
          ))}
        </>
      ) : (
        <>
          <div className="toolbar">
            <h3>
              {" "}
              {t("ui.s00d60e31a4")} {run.id} · {run.mode.replaceAll("_", " ")}
            </h3>
            <button
              disabled={busy}
              onClick={async () => {
                try {
                  await api(`/practice/${run.id}/finish`, "POST", {});
                } catch (e) {
                  setError(String(e));
                  return;
                }
                setRun(undefined);
                setSession(undefined);
                setFeedback(null);
              }}
            >
              {" "}
              {t("ui.s5f3641135a")}{" "}
            </button>
          </div>
          {session && (
            <article>
              <p>
                {exams.find((e) => e.id === session.subject_id)?.name} ·{" "}
                {session.status}
                {session.countdown_visible &&
                  ` · ${t("dynamic.remaining", { time: `${Math.floor(session.remaining_seconds / 60)}:${String(session.remaining_seconds % 60).padStart(2, "0")}` })}`}
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
                    ? t("ui.s32b787c4af")
                    : t("ui.sea2c732683")}
                </button>
              )}
              {active && (
                <>
                  <h3>{session.current_question?.question_text}</h3>
                  <textarea
                    aria-label={t("ui.sb6733159ba")}
                    placeholder={t("ui.s3ec2097bdc")}
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
                    {" "}
                    {t("ui.sb896ada546")}{" "}
                  </button>
                  <button
                    disabled={busy || session.status !== "answering"}
                    onClick={() => act(() => submit(true))}
                  >
                    {" "}
                    {t("ui.s53b3a211e4")}{" "}
                  </button>
                  <Sources
                    exam={session.subject_id}
                    sources={session.sources || []}
                  />
                </>
              )}
              {["completed", "time_expired"].includes(session.status) && (
                <p> {t("ui.s0a12b202b3")} </p>
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
                  {" "}
                  {t("ui.s25a1aa2a41")}{" "}
                </button>
              )}
              {s.evaluation && (
                <p>
                  {s.evaluation.percent_correct}
                  {t("ui.s168d73ac14")} {s.evaluation.german_grade}
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
            {" "}
            {t("ui.s798048576d")}{" "}
          </button>
          {run.overall_evaluation && (
            <p>
              {t("ui.s9d532448e6")} {run.overall_evaluation.german_grade}
            </p>
          )}
        </>
      )}
      <Progress job={job} />
    </section>
  );
}
