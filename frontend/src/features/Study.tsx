import { useEffect, useState } from "react";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress, Sources } from "../components/Common";
import type { Job, Source } from "../types";
export function Study({ exam }: { exam: number }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{
    answer: string;
    contexts: Source[];
  }>();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<
    { id: number; input_text: string; output_text: string; sources: Source[] }[]
  >([]);
  const refresh = () =>
    api<typeof history>(`/exams/${exam}/history`).then(setHistory);
  useEffect(() => {
    void refresh().catch((e) => setError(String(e)));
  }, [exam]);
  async function ask() {
    setBusy(true);
    setError("");
    try {
      setAnswer(await operation(`/exams/${exam}/ask`, { question }, setJob));
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section>
      <h2>Study with your sources</h2>
      <p>Answers use this exam’s accepted evidence.</p>
      <ErrorNotice error={error} />
      <textarea
        aria-label="Question for your course material"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="What would you like to understand?"
      />
      <button disabled={busy || !question.trim()} onClick={ask}>
        Ask local AI
      </button>
      <Progress job={job} />
      {answer && (
        <article>
          <p className="prose">{answer.answer}</p>
          <Sources exam={exam} sources={answer.contexts} />
        </article>
      )}
      <h3>Question history</h3>
      {history.map((h, i) => (
        <details key={h.id || i}>
          <summary>{h.input_text}</summary>
          <p className="prose">{h.output_text}</p>
          <Sources exam={exam} sources={h.sources || []} />
        </details>
      ))}
    </section>
  );
}
interface Plan {
  focus: string;
  recommendations: { action: string; reason: string }[];
  coverage: { topic_name: string; material_state: string }[];
  sections: { id: number; title?: string; content?: string }[];
}
export function StudyPlan({ exam }: { exam: number }) {
  const [plan, setPlan] = useState<Plan>();
  const [days, setDays] = useState(5);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [pack, setPack] = useState<
    {
      id: number;
      concept?: string;
      content?: { oral_answer?: string; must_know?: { text: string }[] };
      quality_status: string;
    }[]
  >([]);
  async function refresh() {
    setPlan(await api<Plan>(`/exams/${exam}/study-plan?days=${days}`));
    setPack(await api<typeof pack>(`/exams/${exam}/exam-pack`));
  }
  useEffect(() => {
    void refresh().catch((e) => setError(String(e)));
  }, [exam, days]);
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
  return (
    <section>
      <h2>Five-day study plan</h2>
      <ErrorNotice error={error} />
      <label>
        Days remaining
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[5, 4, 3, 2, 1].map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
      </label>
      {!plan ? (
        <p>Loading plan…</p>
      ) : (
        <>
          <h3>{plan.focus}</h3>
          {plan.recommendations.map((r, i) => (
            <article key={i}>
              <strong>{r.action}</strong>
              <p>{r.reason}</p>
            </article>
          ))}
          <h3>Material coverage</h3>
          {plan.coverage.map((c, i) => (
            <p key={i}>
              {c.topic_name} · {c.material_state}
            </p>
          ))}
        </>
      )}
      <h3>Exam learning cards</h3>
      <button
        disabled={busy}
        onClick={() =>
          act(() => operation(`/exams/${exam}/exam-pack`, {}, setJob))
        }
      >
        Generate exam pack
      </button>
      <Progress job={job} />
      {pack.map((s) => (
        <article key={s.id}>
          <h3>{s.concept}</h3>
          <p>{s.quality_status}</p>
          <p className="prose">{s.content?.oral_answer}</p>
          <ul>
            {s.content?.must_know?.map((p, i) => (
              <li key={i}>{p.text}</li>
            ))}
          </ul>
          {["accepted", "rejected"].map((status) => (
            <button
              key={status}
              disabled={busy}
              onClick={() =>
                act(() =>
                  api(`/exams/${exam}/exam-pack/${s.id}`, "PATCH", { status }),
                )
              }
            >
              {status}
            </button>
          ))}
        </article>
      ))}
    </section>
  );
}
