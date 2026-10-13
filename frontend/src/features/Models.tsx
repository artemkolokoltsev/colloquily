import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress } from "../components/Common";
import type { Job, ModelStatus } from "../types";
export function Models({ onReady }: { onReady?: () => void }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ModelStatus>();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [free, setFree] = useState<number>();
  const refresh = () =>
    api<ModelStatus>("/models/status")
      .then(setStatus)
      .catch((e) => setError(String(e)));
  useEffect(() => {
    void refresh();
    void api<{free_bytes: number}>('/system/storage').then(data => setFree(data.free_bytes)).catch(() => undefined);
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
      <h2>{t('ui.sbe59b6d66c')}</h2>
      <p> {t('ui.s3feb932584')} </p>
      <ErrorNotice error={error} />
      {free !== undefined && <p>{t('dynamic.modelStorage', { gb: new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(free / 1024**3) })}</p>}
      {!status ? (
        <p>{t('ui.s6d6b6cc894')}</p>
      ) : (
        <>
          <p>
            {status.ollama === "available"
              ? t('ui.sab53cee8b6')
              : t('ui.s38059cf32e')}
          </p>
          {status.ollama !== "available" && (
            <article>
              <h3>{t('ui.s7ed17cde1a')}</h3>
              <p> {t('ui.sc549207ef1')}{" "}
                <a
                  href="https://ollama.com/download"
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
                  target="_blank"
                  rel="noreferrer"
                > {t('ui.s672661d756')} </a> {t('ui.s2c0e621fdb')} </p>
              <p>{status.error}</p>
            </article>
          )}
          <button disabled={busy} onClick={refresh}> {t('ui.sfb7099ad8e')} </button>
          {!!status.missing.length && (
            <button
              className="primary"
              disabled={busy || status.ollama !== "available"}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  for (const model of status.missing)
                    await operation("/models/pull", { model }, setJob);
                  await refresh();
                } catch (e) {
                  setError(String(e));
                } finally {
                  setBusy(false);
                }
              }}
            > {t('ui.s22e63945bf')} </button>
          )}
          <details>
            <summary>{t('ui.s5ddbc1e74d')}</summary>
            {status.required.map((model) => (
              <article key={model}>
                <strong>{model}</strong>
                <span>
                  {status.missing.includes(model) ? t('ui.s6be36ca49e') : t('ui.sf8b32f4e92')}
                </span>
                {status.missing.includes(model) && (
                  <button
                    disabled={busy || status.ollama !== "available"}
                    onClick={() => pull(model)}
                  > {t('ui.s8f2fd8eea0')} </button>
                )}
              </article>
            ))}
          </details>
          {status.ollama === "available" && !status.missing.length && (
            <div className="success">
              <p> {t('ui.sed3833c4b3')} </p>
              {onReady && (
                <button className="primary" onClick={onReady}> {t('ui.s9fedeef0fb')} </button>
              )}
            </div>
          )}
        </>
      )}
      <Progress job={job} />
      <p> {t('ui.saa50e918f8')} </p>
    </section>
  );
}
