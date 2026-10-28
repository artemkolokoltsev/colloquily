import { AISetup } from "./AISetup";
import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress } from "../components/Common";
import type { Job, ModelStatus } from "../types";
export function Models({
  exam,
  onReady,
}: {
  exam: number;
  onReady?: () => void;
}) {
  const { t } = useTranslation();
  const [readiness, setReadiness] = useState("checking");
  const [manualBackend, setManualBackend] = useState(false);
  const [status, setStatus] = useState<ModelStatus>();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState<{
    task_models: Record<string, string>;
    embedding_config: { model: string };
  }>();
  const [saved, setSaved] = useState(false);
  const catalog = [
    { name: "qwen2.5:1.5b", size: "≈ 1 GB", detail: "modelSmall" },
    { name: "qwen3:4b", size: "≈ 2.5 GB", detail: "modelBalanced" },
    { name: "qwen3:8b", size: "≈ 5 GB", detail: "modelLarge" },
    { name: "gemma3:4b", size: "≈ 3.3 GB", detail: "modelAlternative" },
  ];
  const refresh = () =>
    Promise.all([
      api<ModelStatus>("/models/status").then(setStatus),
      api<NonNullable<typeof config>>(`/exams/${exam}/models`).then(setConfig),
      api<{ state: string; manual_backend?: boolean }>(
        `/exams/${exam}/models/readiness`,
      ).then((value) => {
        setReadiness(value.state);
        setManualBackend(!!value.manual_backend);
      }),
    ]).catch((e) => setError(String(e)));
  useEffect(() => {
    void refresh();
  }, []);
  async function pull(model: string) {
    setBusy(true);
    setError("");
    try {
      await operation("/models/pull", { model }, setJob);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section>
      <h2>{t("ui.sbe59b6d66c")}</h2>
      <ErrorNotice error={error} />
      {manualBackend ? (
        <article>
          <p>{t("setupFlow.alternative")}</p>
          {onReady && (
            <button onClick={onReady}>{t("setupFlow.continue")}</button>
          )}
        </article>
      ) : (
        <AISetup
          key={`${config?.task_models.answering}:${config?.task_models.answer_evaluation}`}
          exam={exam}
          status={status}
          readiness={readiness}
          refresh={refresh}
          onReady={onReady}
        />
      )}
      {status && (
        <details className="model-advanced">
          <summary>{t("setupFlow.advanced")}</summary>
          <h3>{t("ui.modelLibrary")}</h3>
          <p>{t("ui.modelLibraryIntro")}</p>
          {saved && (
            <p role="status" className="success">
              {t("ui.practiceModelSaved")}
            </p>
          )}
          <div className="model-library">
            {[
              ...catalog,
              ...status.installed
                .filter(
                  (name) =>
                    !catalog.some((item) => item.name === name) &&
                    !/embed|bge|cloud/i.test(name),
                )
                .map((name) => ({
                  name,
                  size: "",
                  detail: "modelAlternative",
                })),
            ].map((model) => {
              const installed = status.installed.includes(model.name);
              return (
                <article key={model.name}>
                  <h4>{model.name}</h4>
                  <span className="status-badge">
                    {installed ? t("ui.sf8b32f4e92") : model.size}
                  </span>
                  <p>{t(`ui.${model.detail}` as "ui.modelSmall")}</p>
                  {installed ? (
                    <button
                      disabled={
                        busy ||
                        !config ||
                        config.task_models.answer_evaluation === model.name
                      }
                      onClick={async () => {
                        if (!config) return;
                        setBusy(true);
                        setError("");
                        setSaved(false);
                        try {
                          await api(`/exams/${exam}/models`, "PATCH", {
                            task_models: {
                              ...config.task_models,
                              answer_evaluation: model.name,
                            },
                            embedding_model: config.embedding_config.model,
                          });
                          await refresh();
                          setSaved(true);
                        } catch (e) {
                          setError(String(e));
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      {t("ui.usePracticeModel")}
                      {config?.task_models.answer_evaluation === model.name
                        ? " ✓"
                        : ""}
                    </button>
                  ) : (
                    <button
                      disabled={busy || status.ollama !== "available"}
                      onClick={() => pull(model.name)}
                    >
                      {t("ui.s8f2fd8eea0")}
                    </button>
                  )}
                </article>
              );
            })}
          </div>
          <details>
            <summary>{t("ui.s5ddbc1e74d")}</summary>
            {status.required.map((model) => (
              <article key={model}>
                <strong>{model}</strong>
                <span>
                  {status.missing.includes(model)
                    ? t("ui.s6be36ca49e")
                    : t("ui.sf8b32f4e92")}
                </span>
                {status.missing.includes(model) && (
                  <button
                    disabled={busy || status.ollama !== "available"}
                    onClick={() => pull(model)}
                  >
                    {" "}
                    {t("ui.s8f2fd8eea0")}{" "}
                  </button>
                )}
              </article>
            ))}
          </details>
        </details>
      )}
      <Progress job={job} />
      <p> {t("ui.saa50e918f8")} </p>
    </section>
  );
}
