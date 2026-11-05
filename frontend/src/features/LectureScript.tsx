import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, apiBytes, downloadBytes } from "../api/client";
import type { LectureScript as Script } from "../types";
import { ErrorNotice } from "../components/Common";

export function LectureScript({
  exam,
  documents,
  disabled,
  onChanged,
}: {
  exam: number;
  documents: { id: number; title: string; relative_path: string }[];
  disabled: boolean;
  onChanged: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [data, setData] = useState<{
    current: Script | null;
    revisions: { revision: number; filename: string }[];
  }>();
  const [existing, setExisting] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void api<typeof data>(
      `/exams/${exam}/lecture-script`,
      "GET",
      undefined,
      controller.signal,
    )
      .then(setData)
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e));
      });
    return () => controller.abort();
  }, [exam]);
  async function upload(file: File) {
    setBusy(true);
    setError("");
    setUpdated(false);
    const form = new FormData();
    form.append("file", file);
    if (existing && !data?.current) form.append("document_id", existing);
    try {
      const result = await api<{ changed: boolean }>(
        `/exams/${exam}/lecture-script`,
        "PUT",
        form,
      );
      setData(await api(`/exams/${exam}/lecture-script`));
      await onChanged();
      setUpdated(result.changed);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="script-card">
      <h3>{t("ui.courseScript")}</h3>
      <p>{t("ui.courseScriptHelp")}</p>
      <ErrorNotice error={error} />
      {data?.current && (
        <p>
          <strong>{data.current.filename}</strong> ·{" "}
          {t("ui.courseRevision", { number: data.current.revision })}
        </p>
      )}
      {data && !data.current && (
        <label>
          {t("ui.courseExisting")}
          <select
            value={existing}
            onChange={(e) => setExisting(e.target.value)}
            disabled={busy || disabled}
          >
            <option value="">{t("ui.courseNewScript")}</option>
            {documents
              .filter((d) => d.relative_path.toLowerCase().endsWith(".pdf"))
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
          </select>
        </label>
      )}
      <label>
        {t(data?.current ? "ui.courseUpdateScript" : "ui.courseUploadScript")}
        <input
          type="file"
          accept=".pdf"
          disabled={busy || disabled || !data}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
            e.target.value = "";
          }}
        />
      </label>
      {busy && <p role="status">{t("ui.courseSaving")}</p>}
      {updated && <p role="status">{t("ui.courseScriptUpdated")}</p>}
      {!!data?.revisions.length && (
        <details>
          <summary>{t("ui.courseHistory")}</summary>
          <p>{t("ui.courseHistoryHelp")}</p>
          {data.revisions.map((r) => (
            <div key={r.revision} className="toolbar">
              <span>
                {r.filename} · {r.revision}
              </span>
              <button
                onClick={() =>
                  void apiBytes(
                    `/exams/${exam}/lecture-script/revisions/${r.revision}`,
                  )
                    .then((bytes) =>
                      downloadBytes(
                        bytes,
                        `script-v${r.revision}.pdf`,
                        "application/pdf",
                      ),
                    )
                    .catch((e) => setError(String(e)))
                }
              >
                {t("ui.courseDownloadPdf")}
              </button>
              <button
                onClick={() =>
                  void apiBytes(
                    `/exams/${exam}/lecture-script/revisions/${r.revision}/notes`,
                  )
                    .then((bytes) =>
                      downloadBytes(
                        bytes,
                        `notes-v${r.revision}.json`,
                        "application/json",
                      ),
                    )
                    .catch((e) => setError(String(e)))
                }
              >
                {t("ui.courseDownloadNotes")}
              </button>
            </div>
          ))}
        </details>
      )}
    </article>
  );
}
