import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorNotice } from "../components/Common";
import { useTranslation } from "react-i18next";
import { checkForUpdate, installPendingUpdate } from "../update";
interface SettingsData {
  values: Record<string, string | number | boolean>;
  data_directory: string;
  sections: {
    section: string;
    fields: { key: string; label: string; type: string; options?: string[] }[];
  }[];
}
export function Settings({ exam }: { exam: number }) {
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<SettingsData>();
  const [models, setModels] = useState<{
    task_models: Record<string, string>;
    embedding_config: { model: string };
  }>();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [version, setVersion] = useState("0.1.0");
  const [updateVersion, setUpdateVersion] = useState("");
  const [updateProgress, setUpdateProgress] = useState<number | null>();
  useEffect(() => {
    Promise.all([
      api<SettingsData>("/settings").then(setData),
      api<NonNullable<typeof models>>(`/exams/${exam}/models`).then(setModels),
    ]).catch((e) => setError(String(e)));
  }, [exam]);
  useEffect(() => {
    if ("__TAURI_INTERNALS__" in window) import("@tauri-apps/api/app").then(({ getVersion }) => getVersion()).then(setVersion).catch(() => undefined);
  }, []);
  async function save() {
    setError("");
    try {
      await api("/settings", "PATCH", { values: data?.values });
      if (models)
        await api(`/exams/${exam}/models`, "PATCH", {
          task_models: models.task_models,
          embedding_model: models.embedding_config.model,
        });
      setMessage(
        t("settings.saved"),
      );
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <section>
      <h2>{t("settings.title")}</h2>
      <p>{t("settings.intro")}</p>
      <ErrorNotice error={error} />
      <p role="status">{message}</p>
      <label>{t("settings.language")}
        <select value={i18n.resolvedLanguage || "en"} onChange={(event) => void i18n.changeLanguage(event.target.value)}>
          <option value="de">{t("settings.german")}</option>
          <option value="en">{t("settings.english")}</option>
        </select>
      </label>
      <p>{t("settings.dataDirectory", { path: data?.data_directory || "…" })}</p>
      <fieldset>
        <legend>{t("settings.backup")}</legend>
        <button onClick={() => { setError(""); void api<{path: string}>("/backups", "POST", {}).then((result) => setMessage(t("settings.backupReady", { path: result.path }))).catch((e) => setError(String(e))); }}>{t("settings.createBackup")}</button>
      </fieldset>
      <fieldset>
        <legend>{t("settings.updates")}</legend>
        <p>{t("settings.currentVersion", { version })}</p>
        <button onClick={() => { setError(""); void checkForUpdate().then((update) => { setUpdateVersion(update?.version || ""); setMessage(update ? t("settings.updateAvailable", { version: update.version }) : t("settings.noUpdate")); }).catch(() => setError(t("settings.updateFailed"))); }}>{t("settings.checkUpdates")}</button>
        {updateVersion && <button onClick={() => void installPendingUpdate(setUpdateProgress).catch(() => setError(t("settings.updateFailed")))}>{t("settings.installUpdate")}</button>}
        {updateProgress !== undefined && <progress max={100} value={updateProgress ?? undefined} />}
      </fieldset>
      {models && (
        <fieldset>
          <legend>{t("settings.models")}</legend>
          {Object.entries(models.task_models).map(([task, value]) => (
            <label key={task}>
              {task.replaceAll("_", " ")}
              <input
                value={value}
                onChange={(e) =>
                  setModels({
                    ...models,
                    task_models: {
                      ...models.task_models,
                      [task]: e.target.value,
                    },
                  })
                }
              />
            </label>
          ))}
          <label>
            {t("settings.embedding")}
            <input
              value={models.embedding_config.model}
              onChange={(e) =>
                setModels({
                  ...models,
                  embedding_config: { model: e.target.value },
                })
              }
            />
          </label>
        </fieldset>
      )}
      {data?.sections.map((s) => (
        <details key={s.section}>
          <summary>{s.section}</summary>
          {s.fields
            .filter((f) => f.key !== "ST_ALLOW_DOWNLOAD")
            .map((f) => (
              <label key={f.key}>
                {f.label}
                {f.type === "bool" ? (
                  <input
                    type="checkbox"
                    checked={!!data.values[f.key]}
                    onChange={(e) =>
                      setData({
                        ...data,
                        values: { ...data.values, [f.key]: e.target.checked },
                      })
                    }
                  />
                ) : f.type === "select" ? (
                  <select
                    value={String(data.values[f.key])}
                    onChange={(e) =>
                      setData({
                        ...data,
                        values: { ...data.values, [f.key]: e.target.value },
                      })
                    }
                  >
                    {f.options?.map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    value={String(data.values[f.key] ?? "")}
                    onChange={(e) =>
                      setData({
                        ...data,
                        values: { ...data.values, [f.key]: e.target.value },
                      })
                    }
                  />
                )}
              </label>
            ))}
        </details>
      ))}
      <button onClick={save}>{t("settings.save")}</button>
    </section>
  );
}
