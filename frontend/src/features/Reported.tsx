import { useEffect, useState } from "react";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress } from "../components/Common";
import type { Job } from "../types";
export function Reported({ exam }: { exam: number }) {
  const [items, setItems] = useState<
    {
      id: number;
      wording_source: string;
      provenance: string;
      reliability: string;
      activation_status: string;
    }[]
  >([]);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = () =>
    api<typeof items>(`/exams/${exam}/reported-questions`).then(setItems);
  useEffect(() => {
    void refresh().catch((e) => setError(String(e)));
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
  return (
    <section>
      <h2>Reported exam questions</h2>
      <p>
        Import a schema 1.0 question bank. Its exam IDs must match existing exam
        slugs; original wording and provenance are preserved.
      </p>
      <ErrorNotice error={error} />
      <label>
        Question bank JSON
        <input
          type="file"
          accept=".json"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file)
              void act(async () =>
                api(
                  "/reported-questions/import",
                  "POST",
                  JSON.parse(await file.text()),
                ),
              );
          }}
        />
      </label>
      <button
        disabled={busy}
        onClick={() =>
          act(() =>
            operation(`/exams/${exam}/reported-questions/ground`, {}, setJob),
          )
        }
      >
        Create evidence-grounded training cards
      </button>
      <button
        disabled={busy}
        onClick={() =>
          act(async () => {
            const bank = await api(`/exams/${exam}/reported-questions/export`);
            const url = URL.createObjectURL(
              new Blob([JSON.stringify(bank, null, 2)], {
                type: "application/json",
              }),
            );
            const a = document.createElement("a");
            a.href = url;
            a.download = "reported-questions.json";
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          })
        }
      >
        Export question bank
      </button>
      <Progress job={job} />
      {!items.length && <p>No reported questions in this exam.</p>}
      {items.map((q) => (
        <article key={q.id}>
          <h3>{q.wording_source}</h3>
          <p>
            {q.provenance} · {q.reliability} · {q.activation_status}
          </p>
        </article>
      ))}
    </section>
  );
}
