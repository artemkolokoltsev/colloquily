import { useEffect, useState } from "react";
import { api, connect } from "../api/client";
import type { Exam } from "../types";
import { ErrorNotice } from "../components/Common";
import { ExamEditor } from "../features/ExamEditor";
import { ProgressPage } from "../features/ProgressPage";
import { Reported } from "../features/Reported";
import { Models } from "../features/Models";
import { Materials } from "../features/Materials";
import { Questions } from "../features/Questions";
import { Practice } from "../features/Practice";
import { Study, StudyPlan } from "../features/Study";
import { Settings } from "../features/Settings";
import { Dashboard } from "../features/Dashboard";
import { useTranslation } from "react-i18next";
import { checkForUpdate } from "../update";
import { ExamPicker } from "../components/ExamPicker";
import { operation } from "../api/client";
import { Progress } from "../components/Common";
import type { Job } from "../types";
const pages = [
  "Dashboard",
  "Materials",
  "Practice",
  "Study",
  "Advanced settings",
] as const;
const pageLabels = {
  Dashboard: "nav.dashboard",
  Materials: "nav.materials",
  Questions: "nav.questions",
  Practice: "nav.practice",
  Progress: "nav.progress",
  Study: "nav.ask",
  "Advanced settings": "nav.settings",
} as const;
const advancedPages = ["Reported questions", "Study plan", "Local AI"];
export default function App() {
  const { t, i18n } = useTranslation();
  const [welcomed, setWelcomed] = useState(
    () => localStorage.getItem("colloquily.welcomed") === "true",
  );
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [exams, setExams] = useState<Exam[]>([]);
  const [selected, setSelected] = useState(0);
  const [page, setPage] = useState("Dashboard");
  const [topic, setTopic] = useState("");
  const [practiceCount, setPracticeCount] = useState(10);
  function navigate(next: string, selectedTopic = "", count = 10) {
    setTopic(selectedTopic);
    setPracticeCount(count);
    setPage(next);
  }
  const [name, setName] = useState("");
  const [examDate, setExamDate] = useState("");
  const [aiSetup, setAiSetup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [aiJob, setAiJob] = useState<Job | null>(null);
  const [aiError, setAiError] = useState("");
  const [aiRetry, setAiRetry] = useState(0);
  function switchExam(id: number) {
    setSelected(id);
    setAiJob(null);
    setAiError("");
    setAiSetup(false);
    setTopic("");
    setPracticeCount(10);
    setAiRetry(0);
  }
  useEffect(() => {
    if (!ready || !selected) return;
    let current = true;
    const controller = new AbortController();
    setAiError("");
    setAiSetup(false);
    setAiJob(null);
    void api<{ state: string }>(
      `/exams/${selected}/models/readiness`,
      "GET",
      undefined,
      controller.signal,
    )
      .then(async (status) => {
        if (!current) return;
        setAiSetup(false);
        if (status.state === "ready") return;
        if (status.state === "ollama_unavailable") {
          setAiSetup(true);
          return;
        }
        if (status.state === "insufficient_storage") {
          setAiError(t("ui.aiStorage"));
          return;
        }
        if (status.state === "failed" && aiRetry === 0) {
          setAiError(t("ui.aiFailed"));
          return;
        }
        await operation(
          `/exams/${selected}/models/prepare`,
          {},
          (job) => {
            if (current) setAiJob(job);
          },
          controller.signal,
        );
      })
      .catch((error) => {
        if (current) {
          setAiError(String(error));
          setAiSetup(true);
        }
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [ready, selected, aiRetry]);
  async function refresh() {
    const e = await api<Exam[]>("/exams");
    setExams(e);
    setSelected((s) => (e.some((v) => v.id === s) ? s : e[0]?.id || 0));
    return e;
  }
  async function start() {
    setError("");
    try {
      await connect();
      const preferences = await api<{ language?: string }>("/preferences");
      if (preferences.language) await i18n.changeLanguage(preferences.language);
      else
        await api("/preferences", "PATCH", {
          language: i18n.resolvedLanguage || "en",
        });
      const existing = await refresh();
      if (!existing.length) setPage("Exams");
      else {
        const [files, prep] = await Promise.all([
          api<{ raw: string[] }>(`/exams/${existing[0].id}/documents`),
          api<{ questions: number }>(`/exams/${existing[0].id}/preparation`),
        ]);
        if (
          existing.length === 1 &&
          existing[0].slug === "imported-exam" &&
          !files.raw.length &&
          !prep.questions
        )
          setPage("Exams");
        else if (!prep.questions) setPage("Materials");
      }
      setReady(true);
      // Update checks are best-effort and never block local study.
      void checkForUpdate().catch(() => undefined);
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    void start();
  }, []);
  async function create() {
    setBusy(true);
    setError("");
    try {
      await api("/preferences", "PATCH", {
        language: i18n.resolvedLanguage || "en",
      });
      const exam = await api<Exam>("/exams", "POST", {
        name: name.trim(),
        exam_date: examDate || null,
        language: i18n.resolvedLanguage || "en",
      });
      await refresh();
      localStorage.setItem("colloquily.welcomed", "true");
      setWelcomed(true);
      setSelected(exam.id);
      setName("");
      setExamDate("");
      setPage("Materials");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  if (!ready)
    return (
      <main className="startup">
        <h1 className="brand">
          <img src="/favicon.svg" alt="" />
          Colloquily
        </h1>
        <p>{t("startup.starting")}</p>
        <ErrorNotice error={error} />
        {error && <button onClick={start}>{t("startup.retry")}</button>}
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <h1 className="brand">
          <img src="/favicon.svg" alt="" />
          Colloquily
        </h1>
        <p className="muted">{t("app.tagline")}</p>
        <ExamPicker
          exams={exams}
          selected={selected}
          onSelect={switchExam}
          onCreate={() => navigate("Exams")}
        />
        <nav aria-label="Your learning">
          {pages.map((p) => (
            <button
              className={
                p === page ||
                (p === "Practice" && page === "Questions") ||
                (p === "Dashboard" && page === "Progress")
                  ? "active"
                  : ""
              }
              key={p}
              aria-current={
                p === page ||
                (p === "Practice" && page === "Questions") ||
                (p === "Dashboard" && page === "Progress")
                  ? "page"
                  : undefined
              }
              disabled={!selected}
              onClick={() => navigate(p)}
            >
              {t(pageLabels[p])}
            </button>
          ))}
        </nav>
        <details className="advanced-nav">
          <summary>{t("nav.advanced")}</summary>
          <nav aria-label="Advanced tools">
            {advancedPages.map((p) => (
              <button
                key={p}
                className={page === p ? "active" : ""}
                disabled={!selected}
                onClick={() => navigate(p)}
              >
                {p === "Local AI"
                  ? t("nav.ai")
                  : p === "Reported questions"
                    ? t("nav.reported")
                    : p === "Study plan"
                      ? t("nav.plan")
                      : t("nav.settings")}
              </button>
            ))}
          </nav>
        </details>
        <small>{t("app.localPromise")}</small>
      </aside>
      <main>
        <header className="window-toolbar">
          <strong>
            {exams.find((exam) => exam.id === selected)?.name || "Colloquily"}
          </strong>
          <span>{t("app.localPromise")}</span>
        </header>
        <ErrorNotice error={error} />
        {["Exams", "Materials", "Local AI", "Practice"].includes(page) && (
          <ol className="setup-steps" aria-label={t("ui.setupSteps")}>
            {[
              ["Exams", "topicStep"],
              ["Materials", "pdfStep"],
              ["Local AI", "aiStep"],
              ["Practice", "practiceStep"],
            ].map(([target, label], index) => (
              <li key={target}>
                <button
                  disabled={!selected && index > 0}
                  aria-current={page === target ? "step" : undefined}
                  onClick={() => navigate(target)}
                >
                  <span>{index + 1}</span>
                  {t(`ui.${label}` as "ui.topicStep")}
                </button>
              </li>
            ))}
          </ol>
        )}
        {aiJob && ["queued", "running"].includes(aiJob.status) && (
          <div className="setup-notice" role="status">
            {t("ui.redesignPreparingAI")}
            <Progress job={aiJob} />
            <button onClick={() => void api("/models/cancel", "POST", {})}>
              {t("ui.redesignCancel")}
            </button>
          </div>
        )}
        {aiError && (
          <div className="setup-notice">
            <ErrorNotice error={aiError} />
            <button onClick={() => setAiRetry((value) => value + 1)}>
              {t("startup.retry")}
            </button>
          </div>
        )}
        {!welcomed && !exams.length && (
          <section>
            <h2>{t("release.welcome")}</h2>
            <label>
              {t("settings.language")}
              <select
                value={i18n.resolvedLanguage || "en"}
                onChange={(event) =>
                  void i18n.changeLanguage(event.target.value)
                }
              >
                <option value="de">Deutsch</option>
                <option value="en">English</option>
              </select>
            </label>
            <p>{t("release.privacy")}</p>
          </section>
        )}
        {aiSetup && page !== "Local AI" && (
          <div className="setup-notice">
            {t("setup.notice")}{" "}
            <button onClick={() => navigate("Local AI")}>
              {t("setup.action")}
            </button>
          </div>
        )}
        {page === "Exams" && (
          <section>
            <p className="eyebrow">{t("exam.eyebrow")}</p>
            <h2>{t("exam.title")}</h2>
            <p>{t("exam.intro")}</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void create();
              }}
            >
              <label>
                {t("exam.name")}
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("exam.placeholder")}
                />
              </label>
              <label>
                {t("exam.date")}{" "}
                <span className="muted">({t("exam.optional")})</span>
                <input
                  type="date"
                  value={examDate}
                  onChange={(e) => setExamDate(e.target.value)}
                />
              </label>
              <button className="primary" disabled={busy || !name.trim()}>
                {t("exam.create")}
              </button>
            </form>
            <div className="cards">
              {exams.map((e) => (
                <article key={e.id}>
                  <h3>{e.name}</h3>
                  <p>{e.description || t("exam.defaultDescription")}</p>
                  <p>{t("exam.minutes", { count: e.exam_duration_minutes })}</p>
                  <button
                    onClick={() => {
                      switchExam(e.id);
                      setPage("Materials");
                    }}
                  >
                    {t("exam.open")}
                  </button>
                  <ExamEditor
                    exam={e}
                    onSaved={async () => {
                      await refresh();
                    }}
                  />
                </article>
              ))}
            </div>
          </section>
        )}
        {page === "Local AI" && (
          <Models
            key={selected}
            exam={selected}
            onReady={() => {
              setAiSetup(false);
              setAiError("");
              setAiRetry((value) => value + 1);
              navigate("Materials");
            }}
          />
        )}
        {page === "Advanced settings" && (
          <Settings key={selected} exam={selected} />
        )}
        {selected > 0 && (
          <div key={`${page}:${selected}`}>
            {page === "Dashboard" && (
              <Dashboard
                exam={exams.find((e) => e.id === selected)!}
                navigate={navigate}
              />
            )}
            {page === "Materials" && (
              <Materials
                exam={selected}
                onPractice={() => navigate("Practice")}
                onSetup={() => navigate("Local AI")}
              />
            )}{" "}
            {page === "Questions" && (
              <Questions
                exam={selected}
                initialTopic={topic}
                onPractice={(t) => navigate("Practice", t)}
              />
            )}{" "}
            {page === "Reported questions" && <Reported exam={selected} />}{" "}
            {page === "Study" && <Study exam={selected} />}{" "}
            {(page === "Practice" || page === "Questions") && (
              <div className="toolbar">
                <button
                  aria-pressed={page === "Practice"}
                  onClick={() => navigate("Practice")}
                >
                  {t("nav.practice")}
                </button>
                <button
                  aria-pressed={page === "Questions"}
                  onClick={() => navigate("Questions")}
                >
                  {t("ui.manageQuestions")}
                </button>
              </div>
            )}
            {page === "Practice" && (
              <Practice
                exams={exams}
                selected={selected}
                initialTopic={topic}
                initialCount={practiceCount}
              />
            )}{" "}
            {page === "Progress" && (
              <>
                <button onClick={() => navigate("Dashboard")}>
                  {t("ui.backHome")}
                </button>
                <ProgressPage exam={selected} />
              </>
            )}{" "}
            {page === "Study plan" && <StudyPlan exam={selected} />}{" "}
          </div>
        )}
      </main>
    </div>
  );
}
