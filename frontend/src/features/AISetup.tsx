import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress } from "../components/Common";
import type { Job, ModelStatus } from "../types";
interface Plan {
  task_models: Record<string, string>;
  missing: string[];
  download_bytes_estimate: number;
  disk_ok: boolean;
  limited_hardware: boolean;
  hardware: { ram_bytes: number; free_bytes: number; architecture: string };
}
export function AISetup({
  exam,
  status,
  readiness,
  refresh,
  onReady,
}: {
  exam: number;
  status?: ModelStatus;
  readiness: string;
  refresh: () => Promise<unknown>;
  onReady?: () => void;
}) {
  const { t } = useTranslation();
  const [plan, setPlan] = useState<Plan>();
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [action, setAction] = useState("");
  const [error, setError] = useState("");
  const [test, setTest] = useState<{
    response_seconds: number;
    slow: boolean;
  }>();
  const running = status?.ollama === "available";
  const gb = (bytes: number) => (bytes / 1024 ** 3).toFixed(1);
  useEffect(() => {
    let active = true;
    setTest(undefined);
    void api<Plan>(`/exams/${exam}/models/recommendation`)
      .then((value) => {
        if (active) setPlan(value);
      })
      .catch((e) => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, [exam, readiness, running]);
  useEffect(() => {
    if (running) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [running, exam]);
  async function work(action: "start" | "prepare" | "verify") {
    setAction(action);
    setBusy(true);
    setError("");
    setTest(undefined);
    setJob(null);
    try {
      const result = await operation<{
        response_seconds: number;
        slow: boolean;
      }>(
        action === "start"
          ? "/models/start"
          : `/exams/${exam}/models/${action}`,
        {},
        setJob,
      );
      await refresh();
      setPlan(await api<Plan>(`/exams/${exam}/models/recommendation`));
      if (action === "verify") setTest(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="ai-setup">
      <p>{t("setupFlow.intro")}</p>
      <ErrorNotice error={error} />
      <ol className="ai-setup-list">
        <li>
          <h3>{t("setupFlow.runtime")}</h3>
          <p>
            {t(
              running
                ? "setupFlow.runtimeReady"
                : status?.ollama === "not_running"
                  ? "setupFlow.runtimeStopped"
                  : "setupFlow.runtimeMissing",
            )}
          </p>
          {!running && (
            <>
              <a
                href="https://ollama.com/download"
                target="_blank"
                rel="noreferrer"
                onClick={async (event) => {
                  if ("__TAURI_INTERNALS__" in window) {
                    event.preventDefault();
                    try {
                      const { invoke } = await import("@tauri-apps/api/core");
                      await invoke("open_ollama_download");
                    } catch (e) {
                      setError(String(e));
                    }
                  }
                }}
              >
                {t("setupFlow.install")}
              </a>
              <p className="muted">{t("setupFlow.installHelp")}</p>
              <button
                disabled={busy || !status}
                onClick={() => void work("start")}
              >
                {t("setupFlow.start")}
              </button>
            </>
          )}
        </li>
        <li>
          <h3>{t("setupFlow.models")}</h3>
          {plan ? (
            <>
              <p>
                {t("setupFlow.hardware", {
                  ram: gb(plan.hardware.ram_bytes),
                  disk: gb(plan.hardware.free_bytes),
                  arch: plan.hardware.architecture,
                })}
              </p>
              <p>
                {t("setupFlow.recommendation", {
                  model: plan.task_models.answering,
                  size: gb(plan.download_bytes_estimate),
                })}
              </p>
              <p className="muted">{t("setupFlow.estimate")}</p>
              {plan.limited_hardware && <p>{t("setupFlow.limited")}</p>}
              {!plan.disk_ok && <p role="alert">{t("setupFlow.disk")}</p>}
              {!!plan.missing.length && (
                <p>
                  {t("setupFlow.missing", { models: plan.missing.join(", ") })}
                </p>
              )}
              {readiness !== "ready" && (
                <button
                  className="primary"
                  disabled={busy || !running || !plan.disk_ok}
                  onClick={() => void work("prepare")}
                >
                  {t("setupFlow.prepare")}
                </button>
              )}
              {readiness === "ready" && <p>{t("setupFlow.modelsReady")}</p>}
            </>
          ) : (
            <p>{t("setupFlow.checking")}</p>
          )}
        </li>
        <li>
          <h3>{t("setupFlow.verify")}</h3>
          <p>{t("setupFlow.verifyHelp")}</p>
          <button
            className="primary"
            disabled={busy || !running || readiness !== "ready"}
            onClick={() => void work("verify")}
          >
            {t("setupFlow.test")}
          </button>
          {test && (
            <div role="status">
              <p>
                {t("setupFlow.testReady", { seconds: test.response_seconds })}
              </p>
              {test.slow && <p>{t("setupFlow.slow")}</p>}
              {onReady && (
                <button className="primary" onClick={onReady}>
                  {t("setupFlow.continue")}
                </button>
              )}
            </div>
          )}
        </li>
      </ol>
      <Progress job={job} />
      {busy && job && job.status !== "completed" && (
        <p>{t("setupFlow.wait")}</p>
      )}
      {busy && action === "prepare" && (
        <button
          onClick={() =>
            void api("/models/cancel", "POST", {}).catch((e) =>
              setError(String(e)),
            )
          }
        >
          {t("setupFlow.cancel")}
        </button>
      )}
      <p className="muted">{t("setupFlow.privacy")}</p>
    </div>
  );
}
