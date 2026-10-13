import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
      <p className="eyebrow">{t('ui.sac2cb8bf2e')}</p>
      <h2>{t('ui.s969acea333')}</h2>
      <p> {t('ui.s4c217f0366')} </p>
      <ErrorNotice error={error} />
      <label> {t('ui.s9098f1f65b')} <input
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
        <p>{t('ui.s579041d84b')}</p>
      )}
      <article className="preparation-card">
        <h3>
          {preparing
            ? t('ui.s86565c9c89')
            : preparation?.questions
              ? t('ui.s40b3761cb8')
              : t('ui.s34ef570432')}
        </h3>
        <p> {t('ui.s0650bb8705')} </p>
        <button
          className="primary"
          disabled={busy || preparing || processing || !data?.raw.length}
          onClick={() => act(() => api(`/exams/${exam}/prepare`, "POST"))}
        >
          {preparation?.job?.status === "failed"
            ? t('ui.s8c029bc7ca')
            : t('ui.s80a7b9c840')}
        </button>
        {!!preparation?.questions && (
          <button className="primary" onClick={onPractice}> {t('ui.sc69f851732')} </button>
        )}
        <Progress job={preparation?.job || null} />
        {preparation?.job?.status === "failed" && (
          <>
            <ErrorNotice
              error={preparation.job.error || t('ui.sab42b805f9')}
            />
            <button onClick={onSetup}>{t('ui.s7932a732e4')}</button>
          </>
        )}
      </article>
      <details>
        <summary>{t('ui.sc933415600')}</summary>
        <p className="muted"> {t('ui.s29f1fc0e10')} </p>
        <div className="toolbar">
          <select
            aria-label={t('ui.s25aaa653a5')}
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="fast">{t('ui.s5d28dddc38')}</option>
            <option value="deep">{t('ui.s938c8b62b7')}</option>
            <option value="deterministic">{t('ui.s29aa06dc22')}</option>
          </select>
          <button
            disabled={
              busy ||
              ["queued", "running"].includes(data?.processing?.status || "")
            }
            onClick={() =>
              act(() => api(`/exams/${exam}/process`, "POST", { mode }))
            }
          > {t('ui.s9ba15dba5c')} </button>
          <button
            disabled={busy || preparing || processing}
            onClick={() =>
              act(() => api(`/exams/${exam}/process/retry`, "POST"))
            }
          > {t('ui.s2c4517af49')} </button>
          <button
            disabled={busy || preparing || processing}
            onClick={() =>
              act(() => operation(`/exams/${exam}/index`, {}, setJob))
            }
          > {t('ui.s0c123f1916')} </button>
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
        <h3>{t('ui.sbcb9c2e713')}</h3>
        {!units.length && <p>{t('ui.s6adfed4d6a')}</p>}
        {units.map((unit) => (
          <article key={unit.id}>
            <strong>
              {unit.document_title} · {unit.source_location}
            </strong>
            <span>{unit.review_status}</span>
            <textarea
              aria-label={t('ui.sef57bb58eb')}
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
