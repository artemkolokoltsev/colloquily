import { useEffect, useState } from "react";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress, Sources } from "../components/Common";
import type { Job } from "../types";
interface Unit {
  id: number;
  content: string;
  review_status: string;
  document_title: string;
  relative_path: string;
  source_location: string;
}
interface MaterialsData {
  raw: string[];
  documents: { id: number; title: string; status?: string }[];
  processing?: {
    status: string;
    progress_percent: number;
    current_document?: string;
    error_text?: string;
  };
}
export function Materials({
  exam,
  onPractice,
  onSetup,
}: {
  exam: number;
  onPractice: () => void;
  onSetup: () => void;
}) {
  const [preparation, setPreparation] = useState<{
    job: Job | null;
    questions: number;
  }>();
  const [data, setData] = useState<MaterialsData>();
  const [units, setUnits] = useState<Unit[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [mode, setMode] = useState("fast");
  async function refresh() {
    const [d, u, p] = await Promise.all([
      api<MaterialsData>(`/exams/${exam}/documents`),
      api<Unit[]>(`/exams/${exam}/review`),
      api<{ job: Job | null; questions: number }>(`/exams/${exam}/preparation`),
    ]);
    setData(d);
    setUnits(u);
    setPreparation(p);
  }
  useEffect(() => {
    void refresh().catch((e) => setError(String(e)));
    const timer = setInterval(
      () => void refresh().catch((e) => setError(String(e))),
      2500,
    );
    return () => clearInterval(timer);
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
  const preparing = ["queued", "running"].includes(
    preparation?.job?.status || "",
  );
  const processing = ["queued", "running"].includes(
    data?.processing?.status || "",
  );
  return (
    <section>
      <p className="eyebrow">Your exam → Your materials → Your practice</p>
      <h2>Add your lecture PDFs</h2>
      <p>
        Upload your notes, then let Colloquily prepare questions from them. You
        can leave this page while preparation runs.
      </p>
      <ErrorNotice error={error} />
      <label>
        Choose PDFs or notes
        <input
          disabled={busy || preparing || processing}
          type="file"
          multiple
          accept=".pdf,.md,.markdown"
          onChange={(e) => {
            const files = e.target.files;
            if (!files?.length) return;
            const form = new FormData();
            Array.from(files).forEach((f) => form.append("files", f));
            void act(() => api(`/exams/${exam}/documents`, "POST", form));
            e.target.value = "";
          }}
        />
      </label>
      <ul>
        {data?.raw.map((name) => (
          <li key={name}>{name}</li>
        ))}
      </ul>
      {data && !data.raw.length && (
        <p>No material yet. Add your lecture notes above.</p>
      )}
      <article className="preparation-card">
        <h3>
          {preparing
            ? "Getting your practice ready…"
            : preparation?.questions
              ? "You have questions to practise"
              : "Ready when you are"}
        </h3>
        <p>
          We’ll read your files, check the study text, and prepare your first
          questions. Unclear passages stay out of practice.
        </p>
        <button
          className="primary"
          disabled={busy || preparing || processing || !data?.raw.length}
          onClick={() => act(() => api(`/exams/${exam}/prepare`, "POST"))}
        >
          {preparation?.job?.status === "failed"
            ? "Try preparation again"
            : "Prepare my practice"}
        </button>
        {!!preparation?.questions && (
          <button className="primary" onClick={onPractice}>
            Start practising →
          </button>
        )}
        <Progress job={preparation?.job || null} />
        {preparation?.job?.status === "failed" && (
          <>
            <ErrorNotice
              error={preparation.job.error || "Preparation stopped. Try again."}
            />
            <button onClick={onSetup}>Check AI setup</button>
          </>
        )}
      </article>
      <details>
        <summary>Advanced tools · processing & source review</summary>
        <p className="muted">
          Optional controls for inspecting passages or troubleshooting a file.
        </p>
        <div className="toolbar">
          <select
            aria-label="Processing mode"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="fast">Fast processing</option>
            <option value="deep">Deep processing</option>
            <option value="deterministic">Deterministic (no LLM)</option>
          </select>
          <button
            disabled={
              busy ||
              ["queued", "running"].includes(data?.processing?.status || "")
            }
            onClick={() =>
              act(() => api(`/exams/${exam}/process`, "POST", { mode }))
            }
          >
            Process materials
          </button>
          <button
            disabled={busy || preparing || processing}
            onClick={() =>
              act(() => api(`/exams/${exam}/process/retry`, "POST"))
            }
          >
            Resume processing
          </button>
          <button
            disabled={busy || preparing || processing}
            onClick={() =>
              act(() => operation(`/exams/${exam}/index`, {}, setJob))
            }
          >
            Build accepted-evidence index
          </button>
        </div>
        {data?.processing && (
          <div role="status">
            <p>
              {data.processing.status} · {data.processing.current_document}
            </p>
            <progress max="100" value={data.processing.progress_percent} />
            <ErrorNotice error={data.processing.error_text || ""} />
          </div>
        )}
        <Progress job={job} />
        <h3>Evidence review</h3>
        {!units.length && <p>Process materials to see reviewable evidence.</p>}
        {units.map((unit) => (
          <article key={unit.id}>
            <strong>
              {unit.document_title} · {unit.source_location}
            </strong>
            <span>{unit.review_status}</span>
            <textarea
              aria-label="Evidence text"
              defaultValue={unit.content}
              key={`${unit.id}:${unit.content}`}
              onBlur={(e) => {
                if (e.target.value !== unit.content)
                  void act(() =>
                    api(`/exams/${exam}/review/${unit.id}`, "PATCH", {
                      status: unit.review_status,
                      content: e.target.value,
                    }),
                  );
              }}
            />
            <div className="toolbar">
              {["accepted", "needs_review", "rejected"].map((status) => (
                <button
                  disabled={busy || preparing || processing}
                  key={status}
                  onClick={() =>
                    act(() =>
                      api(`/exams/${exam}/review/${unit.id}`, "PATCH", {
                        status,
                      }),
                    )
                  }
                >
                  {status.replace("_", " ")}
                </button>
              ))}
            </div>
            <Sources exam={exam} sources={[unit]} />
          </article>
        ))}
      </details>
    </section>
  );
}
