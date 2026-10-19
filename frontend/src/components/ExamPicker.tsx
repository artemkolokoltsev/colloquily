import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Exam } from "../types";

export function ExamPicker({
  exams,
  selected,
  onSelect,
  onCreate,
}: {
  exams: Exam[];
  selected: number;
  onSelect: (id: number) => void;
  onCreate: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [summaries, setSummaries] = useState<
    Record<
      number,
      { date: string | null; questions: number; practised: number }
    >
  >({});
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    let current = true;
    void Promise.all(
      exams.map(async (exam) => {
        const data = await api<{
          date: string | null;
          questions: number;
          practised: number;
        }>(`/exams/${exam.id}/summary`);
        return [exam.id, data] as const;
      }),
    )
      .then((entries) => {
        if (current) setSummaries(Object.fromEntries(entries));
      })
      .catch(() => undefined);
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", outside);
    return () => {
      current = false;
      document.removeEventListener("pointerdown", outside);
    };
  }, [open, exams]);
  function close() {
    setOpen(false);
    trigger.current?.focus();
  }
  return (
    <div
      className="exam-picker"
      ref={root}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          close();
        }
      }}
    >
      <span className="eyebrow">{t("app.currentExam")}</span>
      <button
        ref={trigger}
        className="exam-trigger"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => {
          setQuery("");
          setOpen(!open);
        }}
      >
        <strong>
          {exams.find((exam) => exam.id === selected)?.name ||
            t("app.createExam")}
        </strong>
        <span aria-hidden="true">⌄</span>
      </button>
      {open && (
        <div
          className="exam-popover"
          role="dialog"
          aria-label={t("app.currentExam")}
        >
          <input
            autoFocus
            type="search"
            value={query}
            placeholder={t("ui.redesignSearchExams")}
            aria-label={t("ui.redesignSearchExams")}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div className="exam-options">
            {exams
              .filter((exam) =>
                exam.name
                  .toLocaleLowerCase()
                  .includes(query.toLocaleLowerCase()),
              )
              .map((exam) => (
                <button
                  key={exam.id}
                  aria-pressed={exam.id === selected}
                  onClick={() => {
                    onSelect(exam.id);
                    close();
                  }}
                >
                  <strong>
                    {exam.name}{" "}
                    {exam.id === selected && (
                      <span aria-label={t("ui.redesignActive")}>✓</span>
                    )}
                  </strong>
                  {summaries[exam.id] && (
                    <small>
                      {summaries[exam.id].date || t("ui.redesignNoDate")} ·{" "}
                      {t("ui.redesignExamProgress", summaries[exam.id])}
                    </small>
                  )}
                </button>
              ))}
          </div>
          <button
            onClick={() => {
              onCreate();
              close();
            }}
          >
            + {t("app.createExam")}
          </button>
        </div>
      )}
    </div>
  );
}
