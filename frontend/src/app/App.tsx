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
const pages = ["Dashboard", "Materials", "Questions", "Practice", "Progress"];
const advancedPages = [
  "Reported questions",
  "Study plan",
  "Local AI",
  "Advanced settings",
];
export default function App() {
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
      const existing = await refresh();
      if (!existing.length) setPage("Exams");
      else if (existing.length === 1 && existing[0].slug === "imported-exam") {
        const [files, prep] = await Promise.all([
          api<{ raw: string[] }>(`/exams/${existing[0].id}/documents`),
          api<{ questions: number }>(`/exams/${existing[0].id}/preparation`),
        ]);
        if (!files.raw.length && !prep.questions) setPage("Exams");
      }
      setReady(true);
      const status = await api<{ ollama: string; missing: string[] }>(
        "/models/status",
      );
      setAiSetup(status.ollama !== "available" || status.missing.length > 0);
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
      const exam = await api<Exam>("/exams", "POST", {
        name,
        exam_date: examDate || null,
      });
      await refresh();
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
        <p>Starting your local study workspace…</p>
        <ErrorNotice error={error} />
        {error && <button onClick={start}>Retry connection</button>}
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <h1 className="brand">
          <img src="/favicon.svg" alt="" />
          Colloquily
        </h1>
        <p className="muted">Your local oral-exam workspace</p>
        <label>
          Current exam
          <select
            value={selected}
            onChange={(e) => setSelected(Number(e.target.value))}
          >
            {exams.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </select>
        </label>
        <button className="primary" onClick={() => navigate("Exams")}>
          + Create an exam
        </button>
        <nav aria-label="Your learning">
          {pages.map((p) => (
            <button
              className={p === page ? "active" : ""}
              key={p}
              aria-current={p === page ? "page" : undefined}
              onClick={() => navigate(p)}
            >
              {p}
            </button>
          ))}
          <button
            className={page === "Study" ? "active" : ""}
            onClick={() => navigate("Study")}
          >
            Ask your materials
          </button>
        </nav>
        <details className="advanced-nav">
          <summary>Advanced tools</summary>
          <nav aria-label="Advanced tools">
            {advancedPages.map((p) => (
              <button
                key={p}
                className={page === p ? "active" : ""}
                onClick={() => navigate(p)}
              >
                {p === "Local AI" ? "AI setup" : p}
              </button>
            ))}
          </nav>
        </details>
        <small>
          Local files. Local inference.
          <br />
          No cloud account.
        </small>
      </aside>
      <main>
        <ErrorNotice error={error} />
        {aiSetup && page !== "Local AI" && (
          <div className="setup-notice">
            One-time setup: your local AI needs to be ready before we can
            prepare questions.{" "}
            <button onClick={() => navigate("Local AI")}>Set up AI</button>
          </div>
        )}
        {page === "Exams" && (
          <section>
            <p className="eyebrow">Prepare with evidence</p>
            <h2>What are you preparing for?</h2>
            <p>
              Name your exam, choose a date, then add your lecture PDFs. We’ll
              prepare your first practice questions.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void create();
              }}
            >
              <label>
                New exam name
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Quantum physics"
                />
              </label>
              <label>
                Exam date <span className="muted">(optional)</span>
                <input
                  type="date"
                  value={examDate}
                  onChange={(e) => setExamDate(e.target.value)}
                />
              </label>
              <button className="primary" disabled={busy || !name.trim()}>
                Create exam & add PDFs →
              </button>
            </form>
            <div className="cards">
              {exams.map((e) => (
                <article key={e.id}>
                  <h3>{e.name}</h3>
                  <p>
                    {e.description ||
                      "PDF and Markdown sources, isolated evidence and practice."}
                  </p>
                  <p>{e.exam_duration_minutes}-minute mock exam</p>
                  <button
                    onClick={() => {
                      setSelected(e.id);
                      setPage("Materials");
                    }}
                  >
                    Open materials
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
            onReady={() => {
              setAiSetup(false);
              navigate("Materials");
            }}
          />
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
            {page === "Practice" && (
              <Practice
                exams={exams}
                selected={selected}
                initialTopic={topic}
                initialCount={practiceCount}
              />
            )}{" "}
            {page === "Progress" && <ProgressPage exam={selected} />}{" "}
            {page === "Study plan" && <StudyPlan exam={selected} />}{" "}
            {page === "Advanced settings" && <Settings exam={selected} />}
          </div>
        )}
      </main>
    </div>
  );
}
