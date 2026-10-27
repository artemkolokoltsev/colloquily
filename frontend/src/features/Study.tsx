import { StudyText } from "../components/StudyText";
import { useTranslation } from "react-i18next";
import { useEffect, useRef, useState } from "react";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress, Sources } from "../components/Common";
import type { Job, Source } from "../types";
interface ChatTurn {
  id: number;
  input_text: string;
  output_text: string;
  sources: Source[];
}
export function Study({ exam }: { exam: number }) {
  const { t } = useTranslation();
  const [includeNotes, setIncludeNotes] = useState(false);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const sending = useRef(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let current = true;
    setHistory([]);
    setLoaded(false);
    void api<ChatTurn[]>(`/exams/${exam}/history`)
      .then((items) => {
        if (current) setHistory(items.slice().reverse());
      })
      .catch((e) => {
        if (current) setError(String(e));
      })
      .finally(() => {
        if (current) setLoaded(true);
      });
    return () => {
      current = false;
    };
  }, [exam]);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [history.length, pending]);
  async function ask() {
    const message = question.trim();
    if (!message || sending.current || !loaded) return;
    sending.current = true;
    setBusy(true);
    setError("");
    setPending(message);
    setQuestion("");
    setJob(null);
    try {
      await operation(
        `/exams/${exam}/ask`,
        {
          question: message,
          include_notes: includeNotes,
          history_ids: history.slice(-4).map((turn) => turn.id),
        },
        setJob,
      );
      const items = await api<ChatTurn[]>(`/exams/${exam}/history`);
      setHistory(items.slice().reverse());
    } catch (e) {
      setError(String(e));
      setQuestion(message);
    } finally {
      setPending("");
      setBusy(false);
      sending.current = false;
    }
  }
  return (
    <section className="study-chat">
      <header>
        <h2>{t("nav.ask")}</h2>
        <p className="muted">{t("ui.chatIntro")}</p>
      </header>
      <div
        className="chat-transcript"
        role="log"
        aria-label={t("ui.chatConversation")}
        aria-live="polite"
      >
        {!history.length && !pending && (
          <p className="chat-empty">
            {t(loaded ? "ui.chatEmpty" : "ui.chatLoading")}
          </p>
        )}
        {history.map((turn) => (
          <div className="chat-turn" key={turn.id}>
            <article className="chat-message chat-user">
              <span className="eyebrow">{t("ui.chatYou")}</span>
              <StudyText>{turn.input_text}</StudyText>
            </article>
            <article className="chat-message chat-assistant">
              <span className="eyebrow">Colloquily</span>
              <StudyText>{turn.output_text}</StudyText>
              {!!turn.sources?.length && (
                <details>
                  <summary>{t("ui.practiceSources")}</summary>
                  <Sources exam={exam} sources={turn.sources} />
                </details>
              )}
            </article>
          </div>
        ))}
        {pending && (
          <>
            <article className="chat-message chat-user">
              <span className="eyebrow">{t("ui.chatYou")}</span>
              <StudyText>{pending}</StudyText>
            </article>
            <p role="status">{t("ui.chatThinking")}</p>
          </>
        )}
        <div ref={end} />
      </div>
      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          void ask();
        }}
      >
        <ErrorNotice error={error} />
        <textarea
          aria-label={t("ui.chatMessage")}
          placeholder={t("ui.chatPlaceholder")}
          value={question}
          disabled={busy || !loaded}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              event.preventDefault();
              void ask();
            }
          }}
        />
        <div className="chat-composer-actions">
          <label className="inline">
            <input
              type="checkbox"
              checked={includeNotes}
              disabled={busy}
              onChange={(event) => setIncludeNotes(event.target.checked)}
            />
            {t("ui.includeNotes")}
          </label>
          <button
            className="primary"
            disabled={busy || !loaded || !question.trim()}
          >
            {t("ui.chatSend")}
          </button>
        </div>
        <small className="muted">{t("ui.chatHint")}</small>
        {busy && <Progress job={job} />}
      </form>
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
  const { t } = useTranslation();
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
      <h2>{t("ui.sdaff920206")}</h2>
      <ErrorNotice error={error} />
      <label>
        {" "}
        {t("ui.sd5b090546f")}{" "}
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[5, 4, 3, 2, 1].map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
      </label>
      {!plan ? (
        <p>{t("ui.sc9773eb959")}</p>
      ) : (
        <>
          <h3>{plan.focus}</h3>
          {plan.recommendations.map((r, i) => (
            <article key={i}>
              <strong>{r.action}</strong>
              <p>{r.reason}</p>
            </article>
          ))}
          <h3>{t("ui.sa352d1efdd")}</h3>
          {plan.coverage.map((c, i) => (
            <p key={i}>
              {c.topic_name} · {c.material_state}
            </p>
          ))}
        </>
      )}
      <h3>{t("ui.s10dc530f8e")}</h3>
      <button
        disabled={busy}
        onClick={() =>
          act(() => operation(`/exams/${exam}/exam-pack`, {}, setJob))
        }
      >
        {" "}
        {t("ui.s7d6c2bd616")}{" "}
      </button>
      <Progress job={job} />
      {pack.map((s) => (
        <article key={s.id}>
          <h3>{s.concept}</h3>
          <p>{s.quality_status}</p>
          <StudyText>{s.content?.oral_answer}</StudyText>
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
