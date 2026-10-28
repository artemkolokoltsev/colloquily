import { useEffect, useState } from "react";
import { api, downloadBackup } from "../api/client";
import { ErrorNotice } from "../components/Common";
import { useTranslation } from "react-i18next";

interface SettingsData {
  values: Record<string, string | number | boolean>;
  data_directory: string;
  sections: {
    section: string;
    fields: { key: string; label: string; type: string; options?: string[] }[];
  }[];
}
export function Settings({
  exam,
  onAbout,
}: {
  exam: number;
  onAbout: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<SettingsData>();
  const [models, setModels] = useState<{
    task_models: Record<string, string>;
    embedding_config: { model: string };
  }>();
  const [error, setError] = useState("");
  const [languageBusy, setLanguageBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [version, setVersion] = useState("0.1.10");
  const [backupFile, setBackupFile] = useState<File>();
  const [backupPreview, setBackupPreview] = useState<{
    created_at: string;
    schema_version: number;
    files: Record<string, string>;
  }>();
  const [busy, setBusy] = useState(false);
  async function inspect(file: File) {
    setError("");
    setBackupPreview(undefined);
    setBackupFile(file);
    const body = new FormData();
    body.append("file", file);
    try {
      setBackupPreview(await api("/backups/inspect", "POST", body));
    } catch (e) {
      setError(String(e));
    }
  }
  async function restore() {
    if (!backupFile || !window.confirm(t("release.confirmRestore"))) return;
    setBusy(true);
    setError("");
    const body = new FormData();
    body.append("file", backupFile);
    try {
      await api("/backups/restore?confirmed=true", "POST", body);
      setMessage(t("release.restored"));
      window.location.reload();
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }
  useEffect(() => {
    Promise.all([
      api<SettingsData>("/settings").then(setData),
      exam
        ? api<NonNullable<typeof models>>(`/exams/${exam}/models`).then(
            setModels,
          )
        : Promise.resolve(),
    ]).catch((e) => setError(String(e)));
  }, [exam]);
  useEffect(() => {
    if ("__TAURI_INTERNALS__" in window)
      import("@tauri-apps/api/app")
        .then(({ getVersion }) => getVersion())
        .then((value) => {
          if (typeof value === "string" && value) setVersion(value);
        })
        .catch(() => undefined);
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
      setMessage(t("settings.saved"));
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <section className="settings-page">
      <h2>{t("settings.title")}</h2>
      <p>{t("settings.intro")}</p>
      <ErrorNotice error={error} />
      <p role="status">{message}</p>
      <section className="settings-card">
        <h3>{t("settings.language")}</h3>
        <p className="muted">{t("ui.languageHelp")}</p>
        <div
          className="language-cards"
          role="group"
          aria-label={t("settings.language")}
        >
          {[
            ["en", "English"],
            ["de", "Deutsch"],
          ].map(([language, label]) => (
            <button
              key={language}
              disabled={languageBusy}
              aria-pressed={(i18n.resolvedLanguage || "en") === language}
              onClick={async () => {
                setLanguageBusy(true);
                setError("");
                try {
                  await api("/preferences", "PATCH", { language });
                  await i18n.changeLanguage(language);
                  setMessage(i18n.t("common.languageChanged"));
                } catch (error) {
                  setError(String(error));
                } finally {
                  setLanguageBusy(false);
                }
              }}
            >
              <strong>{label}</strong>
              <span>{language.toUpperCase()}</span>
            </button>
          ))}
        </div>
      </section>
      <fieldset>
        <legend>{t("settings.backup")}</legend>
        <button
          disabled={busy}
          onClick={() => {
            setError("");
            setBusy(true);
            void api<{ path: string; filename: string }>("/backups", "POST", {})
              .then(async (result) => {
                setMessage(t("settings.backupReady", { path: result.path }));
                await downloadBackup(result.filename);
              })
              .catch((e) => setError(String(e)))
              .finally(() => setBusy(false));
          }}
        >
          {t("settings.createBackup")}
        </button>
        <label>
          {t("release.selectBackup")}
          <input
            disabled={busy}
            type="file"
            accept=".colloquily-backup"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void inspect(file);
            }}
          />
        </label>
        {backupPreview && (
          <>
            <p>
              {t("release.preview", {
                date: new Intl.DateTimeFormat(i18n.resolvedLanguage).format(
                  new Date(backupPreview.created_at),
                ),
                count: Object.keys(backupPreview.files).length,
                schema: backupPreview.schema_version,
              })}
            </p>
            <button disabled={busy} onClick={() => void restore()}>
              {t("release.restore")}
            </button>
          </>
        )}
      </fieldset>
      <fieldset>
        <legend>{t("settings.updates")}</legend>
        <p>{t("settings.currentVersion", { version })}</p>
        <button onClick={onAbout}>{t("ui.aboutTitle")}</button>
      </fieldset>
      <details>
        <summary>{t("nav.advanced")}</summary>
        <p className="storage-path">
          {t("settings.dataDirectory", { path: data?.data_directory || "…" })}
        </p>
        {models && (
          <fieldset>
            <legend>{t("settings.models")}</legend>
            {Object.entries(models.task_models).map(([task, value]) => (
              <label key={task}>
                {t(`dynamic.${task}`, {
                  defaultValue: task.replaceAll("_", " "),
                })}
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
            <summary>
              {t(`dynamic.${s.section}`, { defaultValue: s.section })}
            </summary>
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
      </details>
    </section>
  );
}
