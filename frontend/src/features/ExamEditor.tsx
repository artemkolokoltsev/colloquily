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
      <summary>Edit exam</summary>
      <ErrorNotice error={error} />
      <label>
        Name
        <input
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        />
      </label>
      <label>
        Description
        <input
          value={draft.description}
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
        />
      </label>
      <label>
        Language
        <input
          value={draft.language}
          onChange={(e) => setDraft({ ...draft, language: e.target.value })}
        />
      </label>
      <label>
        Mock duration in minutes
        <input
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
      <button disabled={busy} onClick={() => save()}>
        Save exam
      </button>
      <button disabled={busy} onClick={() => setConfirm(true)}>
        Delete exam…
      </button>
      {confirm && (
        <p>
          Delete this exam and its practice records? Raw files remain on disk.{" "}
          <button disabled={busy} onClick={() => save(true)}>
            Confirm deletion
          </button>
          <button onClick={() => setConfirm(false)}>Cancel</button>
        </p>
      )}
    </details>
  );
}
