import { SessionResults } from "./SessionResults";
import { ModeVisual } from "./ModeVisual";
import { PracticeGuide } from "./PracticeGuide";
import { practiceModes, type PracticeMode } from "./practiceLearning";
import { StudyText } from "../components/StudyText";
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
  const [mode, setMode] = useState<PracticeMode>(
    initialTopic || initialCount > 1 ? "random_practice" : "single_question",
  );
  const [ids, setIds] = useState([selected]);
  const [run, setRun] = useState<Run>();
  const [resumable, setResumable] = useState<Run>();
  const [session, setSession] = useState<Session>();
  const [answer, setAnswer] = useState("");
  const [insightOpen, setInsightOpen] = useState(false);
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [submittedAnswer, setSubmittedAnswer] = useState("");
  const [feedback, setFeedback] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const closed = useRef(false);
  const transitionVersion = useRef(0);
  const [job, setJob] = useState<Job | null>(null);
  const [resumeReady, setResumeReady] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (setupOpen && !run) dialog.current?.showModal();
    else dialog.current?.close();
  }, [setupOpen, run]);
  useEffect(() => {
    document.body.classList.toggle("practice-focus", !!run);
    return () => document.body.classList.remove("practice-focus");
  }, [!!run]);
  useEffect(() => {
    let current = true;
    setResumeReady(false);
    void api<{ id: number; status: string }[]>(
      `/practice?subject_id=${selected}`,
    )
      .then(async (runs) => {
        const pending = runs.find((item) =>
          ["created", "running", "transition"].includes(item.status),
        );
        if (!pending) return;
        const existing = await api<Run>(`/practice/${pending.id}`);
        if (!current) return;
        if (
          existing.sessions.some(
            (part) => !["completed", "time_expired"].includes(part.status),
          )
        )
          setResumable(existing);
      })
      .catch((e) => {
        if (current) setError(String(e));
      })
      .finally(() => {
        if (current) setResumeReady(true);
      });
    return () => {
      current = false;
    };
  }, [selected]);
  const [durationSeconds, setDurationSeconds] = useState(300);
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
  const [availableQuestions, setAvailableQuestions] = useState<number | null>(
    null,
  );
  const [preparation, setPreparation] = useState(0);
  const [started, setStarted] = useState(Date.now());
  useEffect(() => {
    let current = true;
    void api<{ questions: number }>(`/exams/${selected}/preparation`)
      .then((value) => {
        if (current) setAvailableQuestions(value.questions);
      })
      .catch((e) => {
        if (current) setError(String(e));
      });
    return () => {
      current = false;
    };
  }, [selected]);
  useEffect(() => {
    if (!session || closed.current) return;
    if (
      ["completed", "time_expired"].includes(session.status) &&
      ["completed", "failed"].includes(run?.evaluation_status || "")
    )
      return;
    let current = true;
    const timer = setInterval(() => {
      if (submitting.current || closed.current || !current) return;
      const version = transitionVersion.current;
      api<Session>(`/sessions/${session.id}`)
        .then((s) => {
          if (
            !current ||
            closed.current ||
            version !== transitionVersion.current ||
            submitting.current
          )
            return;
          setSession(s);
          if (["completed", "time_expired"].includes(s.status) && run)
            api<Run>(`/practice/${run.id}`)
              .then((result) => {
                if (
                  current &&
                  !closed.current &&
                  version === transitionVersion.current
                )
                  setRun(result);
              })
              .catch((e) => setError(String(e)));
        })
        .catch((e) => setError(String(e)));
    }, 1000);
    return () => {
      current = false;
      clearInterval(timer);
    };
  }, [session?.id, session?.status, run?.id, run?.evaluation_status]);
  useEffect(() => setInsightOpen(false), [session?.current_question?.id]);
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
  async function submit(skip = false) {
    if (!session?.current_question || submitting.current) return;
    const questionId = session.current_question.id;
    submitting.current = true;
    transitionVersion.current += 1;
    setJob(null);
    setFeedback(null);
    try {
      const result = skip
        ? await api<{ session: Session; evaluation: null }>(
            `/sessions/${session.id}/skip`,
            "POST",
            { question_id: questionId },
          )
        : await operation<{
            session: Session;
            evaluation: Evaluation | null;
          }>(
            `/sessions/${session.id}/answer`,
            {
              answer,
              question_id: questionId,
              response_duration_seconds: Math.floor(
                (Date.now() - started) / 1000,
              ),
            },
            setJob,
          );
      setSession(result.session);
      setSubmittedQuestion(session.current_question?.question_text || "");
      setSubmittedAnswer(answer);
      setFeedback(result.evaluation);
      setAnswer("");
      setStarted(Date.now());
      if (run) setRun(await api<Run>(`/practice/${run.id}`));
    } finally {
      submitting.current = false;
    }
  }
  const validSubjectCount =
    mode === "full_colloquium"
      ? ids.length === 3
      : mode === "multi_subject"
        ? ids.length >= 2 && ids.length <= 3
        : true;
  const active = session && ["answering", "preparing"].includes(session.status);
  const completed = run?.sessions.every((s) =>
    ["completed", "time_expired"].includes(s.status),
  );
  async function leave() {
    if (!run) return;
    closed.current = true;
    transitionVersion.current += 1;
    try {
      await api(`/practice/${run.id}/finish`, "POST", {});
    } catch (error) {
      closed.current = false;
      throw error;
    }
    setRun(undefined);
    setSession(undefined);
    setFeedback(null);
    setAnswer("");
  }
  return (
    <section className={run ? "practice-session" : "practice-picker"}>
      {!run && (
        <>
          <p className="eyebrow">{t("nav.practice")}</p>
          <h2>{t("ui.practiceChoose")}</h2>
          <p className="muted">{t("ui.practiceIntro")}</p>
        </>
      )}
      <ErrorNotice error={error} />
      {!run ? (
        <>
          {resumable && (
            <div className="setup-notice">
              <p>{t("ui.practiceResumeHelp")}</p>
              <button
                onClick={() => {
                  closed.current = false;
                  setRun(resumable);
                  setSession(
                    resumable.sessions.find(
                      (item) =>
                        !["completed", "time_expired"].includes(item.status),
                    ) || resumable.sessions.at(-1),
                  );
                  setResumable(undefined);
                }}
              >
                {t("ui.practiceResume")}
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    await api(`/practice/${resumable.id}/finish`, "POST", {});
                    setResumable(undefined);
                  })
                }
              >
                {t("ui.practiceDiscard")}
              </button>
            </div>
          )}
          <div
            className="practice-modes"
            role="group"
            aria-label={t("ui.chooseMode")}
          >
            {practiceModes.map((value) => (
              <button
                key={value}
                className="mode-card"
                aria-haspopup="dialog"
                aria-pressed={setupOpen && mode === value}
                onClick={() => {
                  setMode(value);
                  setDurationSeconds(value === "full_colloquium" ? 900 : 300);
                  setIds([selected]);
                  setError("");
                  setDifficulties("");
                  setPriorities("");
                  setTopics(value === "random_practice" ? initialTopic : "");
                  setSetupOpen(true);
                }}
              >
                <ModeVisual mode={value} />
                <strong>{t(`dynamic.${value}`)}</strong>
                <span>
                  {t(`ui.mode_${value}` as "ui.mode_single_question")}
                </span>
                <span className="mode-focus">
                  {t(`practiceLearning.${value}_focus`)}
                </span>
                <span className="mode-open">
                  {t("ui.practiceExplore")} <span aria-hidden="true">↗</span>
                </span>
              </button>
            ))}
          </div>
          <dialog
            ref={dialog}
            className="practice-dialog"
            aria-labelledby="practice-dialog-title"
            onCancel={(event) => {
              event.preventDefault();
              if (!busy) setSetupOpen(false);
            }}
          >
            <div className="dialog-toolbar">
              <h2 id="practice-dialog-title">{t(`dynamic.${mode}`)}</h2>
              <button
                autoFocus
                disabled={busy}
                onClick={() => setSetupOpen(false)}
                aria-label={t("ui.practiceClose")}
              >
                ×
              </button>
            </div>
            <ModeVisual mode={mode} />
            <PracticeGuide key={mode} mode={mode} />
            <ErrorNotice error={error} />
            {["multi_subject", "full_colloquium"].includes(mode) && (
              <fieldset>
                <legend>{t("ui.s16aaf28e05")}</legend>
                <p>{t("practiceLearning.selectionHelp")}</p>
                {exams.map((e) => (
                  <label className="inline" key={e.id}>
                    <input
                      type="checkbox"
                      checked={ids.includes(e.id)}
                      disabled={!ids.includes(e.id) && ids.length >= 3}
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
            )}
            <fieldset className="timer-options">
              <legend>{t("ui.timerDuration")}</legend>
              <p className="muted">
                {t(
                  ["multi_subject", "full_colloquium"].includes(mode)
                    ? "ui.timerPerSubject"
                    : "ui.timerTotal",
                )}
              </p>
              <div
                className="timer-cards"
                role="group"
                aria-label={t("ui.timerDuration")}
              >
                {[5, 10, 15, 30, 45, 60, 90].map((minutes) => (
                  <button
                    type="button"
                    key={minutes}
                    aria-pressed={durationSeconds === minutes * 60}
                    onClick={() => {
                      setDurationSeconds(minutes * 60);
                      setPreparation((value) =>
                        Math.min(value, minutes * 60 - 15),
                      );
                    }}
                  >
                    <span aria-hidden="true">◷</span>
                    <strong>{minutes}</strong>
                    <small>{t("ui.timerMinutes")}</small>
                  </button>
                ))}
              </div>
            </fieldset>
            <details>
              <summary>{t("ui.sef46ed5421")}</summary>
              <label>
                {" "}
                {t("ui.s2762dc6987")}{" "}
                <input
                  type="number"
                  min="0"
                  max={Math.min(600, durationSeconds - 15)}
                  value={preparation}
                  onChange={(e) => setPreparation(Number(e.target.value))}
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
            {!validSubjectCount && (
              <p role="status">{t("practiceLearning.selectionHelp")}</p>
            )}
            {availableQuestions === 0 && (
              <p className="setup-notice" role="status">
                {t("ui.prepareBeforePractice")}
              </p>
            )}
            <button
              className="primary"
              disabled={
                busy ||
                !resumeReady ||
                !validSubjectCount ||
                !ids.length ||
                ids.length > 3 ||
                (!["multi_subject", "full_colloquium"].includes(mode) &&
                  !availableQuestions)
              }
              onClick={() =>
                act(async () => {
                  if (resumable) {
                    await api(`/practice/${resumable.id}/finish`, "POST", {});
                    setResumable(undefined);
                  }
                  const r = await api<Run>("/practice", "POST", {
                    subject_ids: ["multi_subject", "full_colloquium"].includes(
                      mode,
                    )
                      ? ids
                      : [selected],
                    mode,
                    preparation_seconds: preparation,
                    answer_seconds: 60,
                    session_duration_seconds: durationSeconds,
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
                  closed.current = false;
                  setRun(r);
                  setSetupOpen(false);
                  setSession(r.sessions[0]);
                  setSession(
                    await api<Session>(
                      `/sessions/${r.sessions[0].id}/begin`,
                      "POST",
                    ),
                  );
                  setStarted(Date.now());
                })
              }
            >
              {" "}
              {t("ui.s4954d147d3")}{" "}
            </button>
          </dialog>
        </>
      ) : (
        <>
          <header className="session-toolbar">
            <span>
              {t(`dynamic.${run.mode}`, {
                defaultValue: run.mode.replaceAll("_", " "),
              })}
            </span>
            <span className="session-clock">
              {session?.countdown_visible && active
                ? t("dynamic.remaining", {
                    time: `${Math.floor(session.remaining_seconds / 60)}:${String(session.remaining_seconds % 60).padStart(2, "0")}`,
                  })
                : ""}
            </span>
            {!completed && (
              <button disabled={busy} onClick={() => void act(leave)}>
                {t("ui.practiceExit")}
              </button>
            )}
          </header>
          <div className="session-stage">
            {feedback ? (
              <div className="session-feedback">
                <h2>{t("ui.practiceReflection")}</h2>
                <StudyText>{submittedQuestion}</StudyText>
                <EvaluationView value={feedback} answer={submittedAnswer} />
                <button className="primary" onClick={() => setFeedback(null)}>
                  {t("ui.practiceContinue")}
                </button>
              </div>
            ) : (
              <>
                {session && (
                  <>
                    <p className="eyebrow">
                      {exams.find((e) => e.id === session.subject_id)?.name}
                    </p>
                    {active && (
                      <>
                        <div className="session-question">
                          <StudyText>
                            {session.current_question?.question_text}
                          </StudyText>
                        </div>
                        <label
                          className="answer-label"
                          htmlFor="practice-answer"
                        >
                          {t("ui.sb6733159ba")}
                        </label>
                        <textarea
                          id="practice-answer"
                          autoFocus
                          placeholder={t("ui.s3ec2097bdc")}
                          value={answer}
                          onChange={(event) => setAnswer(event.target.value)}
                          disabled={busy || session.status === "preparing"}
                        />
                        <div className="session-actions">
                          <button
                            className="primary"
                            disabled={
                              busy ||
                              !answer.trim() ||
                              session.status !== "answering"
                            }
                            onClick={() => void act(() => submit())}
                          >
                            {t("ui.sb896ada546")}
                          </button>
                          <button
                            disabled={busy || session.status !== "answering"}
                            onClick={() => void act(() => submit(true))}
                          >
                            {t("ui.s53b3a211e4")}
                          </button>
                        </div>
                        <details
                          className="session-reference"
                          open={insightOpen}
                          onToggle={(event) =>
                            setInsightOpen(event.currentTarget.open)
                          }
                        >
                          <summary>{t("ui.insight")}</summary>
                          {insightOpen && (
                            <Sources
                              exam={session.subject_id}
                              sources={session.sources || []}
                            />
                          )}
                        </details>
                      </>
                    )}
                    {["created", "queued", "transition", "preparing"].includes(
                      session.status,
                    ) && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          void act(async () => {
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
                    {!completed &&
                      ["completed", "time_expired"].includes(
                        session.status,
                      ) && <p>{t("ui.s0a12b202b3")}</p>}
                  </>
                )}
                {!active &&
                  run.sessions
                    .filter(
                      (s) =>
                        ["queued", "created", "transition"].includes(
                          s.status,
                        ) && s.id !== session?.id,
                    )
                    .slice(0, 1)
                    .map((s) => (
                      <button
                        className="primary"
                        key={s.id}
                        disabled={busy}
                        onClick={() =>
                          void act(async () => {
                            setSession(
                              await api<Session>(
                                `/sessions/${s.id}/begin`,
                                "POST",
                              ),
                            );
                            setAnswer("");
                            setStarted(Date.now());
                          })
                        }
                      >
                        {t("ui.practiceNextSubject")} ·{" "}
                        {exams.find((e) => e.id === s.subject_id)?.name}
                      </button>
                    ))}
                {completed && (
                  <div className="session-summary">
                    <h2>{t("ui.practiceComplete")}</h2>
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => void act(leave)}
                    >
                      {t("ui.practiceBack")}
                    </button>
                    {run.evaluation_status === "failed" && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          void act(async () => {
                            await operation(
                              `/practice/${run.id}/evaluate`,
                              {},
                              setJob,
                            );
                            setRun(await api<Run>(`/practice/${run.id}`));
                          })
                        }
                      >
                        {t("ui.retryEvaluation")}
                      </button>
                    )}
                    {["queued", "running"].includes(
                      run.evaluation_status || "",
                    ) && <p role="status">{t("ui.autoEvaluating")}</p>}
                    <Progress job={run.evaluation_job || null} />
                    <SessionResults run={run} exams={exams} />
                  </div>
                )}
              </>
            )}
            <Progress job={job?.status === "completed" ? null : job} />
          </div>
        </>
      )}
    </section>
  );
}
