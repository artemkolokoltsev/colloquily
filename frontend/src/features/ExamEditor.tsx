import { useTranslation } from "react-i18next";
import { useState } from "react";
import { api } from "../api/client";
import type { Exam } from "../types";
import { ErrorNotice } from "../components/Common";
export function ExamEditor({
  exam,
  onSaved,
}: {
  exam: Exam;
  onSaved: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(exam);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  async function save(remove = false) {
    setBusy(true);
    setError("");
    try {
      await api(
        `/exams/${exam.id}`,
        remove ? "DELETE" : "PATCH",
        remove
          ? undefined
          : {
              name: draft.name,
              description: draft.description,
              language: draft.language,
              exam_duration_minutes: draft.exam_duration_minutes,
            },
      );
      await onSaved();
      setConfirm(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <details>
      <summary>{t('ui.s0bbb4f1ba2')}</summary>
      <ErrorNotice error={error} />
      <label> {t('ui.sdcd1d5223f')} <input
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        />
      </label>
      <label> {t('ui.s526e0087cc')} <input
          value={draft.description}
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
        />
      </label>
      <label> {t('ui.sa4fe65264e')} <input
          value={draft.language}
          onChange={(e) => setDraft({ ...draft, language: e.target.value })}
        />
      </label>
      <label> {t('ui.s45fbf7a17c')} <input
          type="number"
          min="1"
          max="240"
          value={draft.exam_duration_minutes}
          onChange={(e) =>
            setDraft({
              ...draft,
              exam_duration_minutes: Number(e.target.value),
            })
          }
        />
      </label>
      <button disabled={busy} onClick={() => save()}> {t('ui.s77d3a2df6c')} </button>
      <button disabled={busy} onClick={() => setConfirm(true)}> {t('ui.s9f9d2a99ea')} </button>
      {confirm && (
        <p> {t('release.deletePreview')}{" "}
          <button disabled={busy} onClick={() => save(true)}> {t('ui.sfa57243dc0')} </button>
          <button onClick={() => setConfirm(false)}>{t('ui.s19766ed6cc')}</button>
        </p>
      )}
    </details>
  );
}
