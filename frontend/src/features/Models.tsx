import { useEffect, useState } from "react";
import { api, operation } from "../api/client";
import { ErrorNotice, Progress } from "../components/Common";
import type { Job, ModelStatus } from "../types";
export function Models({ onReady }: { onReady?: () => void }) {
  const [status, setStatus] = useState<ModelStatus>();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = () =>
    api<ModelStatus>("/models/status")
      .then(setStatus)
      .catch((e) => setError(String(e)));
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
      <h2>Local AI setup</h2>
      <p>
        Your documents stay on this computer. Model downloads require internet
        access and may use several GB of disk space.
      </p>
      <ErrorNotice error={error} />
      {!status ? (
        <p>Checking local AI…</p>
      ) : (
        <>
          <p>
            {status.ollama === "available"
              ? "Your local AI service is running."
              : "Open Ollama to continue setup."}
          </p>
          {status.ollama !== "available" && (
            <article>
              <h3>Install or open Ollama</h3>
              <p>
                Install Ollama from{" "}
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
                >
                  ollama.com/download
                </a>
                , then open the Ollama application. Return here and check again.
              </p>
              <p>{status.error}</p>
            </article>
          )}
          <button disabled={busy} onClick={refresh}>
            Check again
          </button>
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
            >
              Download everything needed
            </button>
          )}
          <details>
            <summary>Model details</summary>
            {status.required.map((model) => (
              <article key={model}>
                <strong>{model}</strong>
                <span>
                  {status.missing.includes(model) ? "Missing" : "Installed"}
                </span>
                {status.missing.includes(model) && (
                  <button
                    disabled={busy || status.ollama !== "available"}
                    onClick={() => pull(model)}
                  >
                    Download AI model
                  </button>
                )}
              </article>
            ))}
          </details>
          {status.ollama === "available" && !status.missing.length && (
            <div className="success">
              <p>
                You’re ready to go. Your files and answers stay on this
                computer.
              </p>
              {onReady && (
                <button className="primary" onClick={onReady}>
                  Continue to my materials →
                </button>
              )}
            </div>
          )}
        </>
      )}
      <Progress job={job} />
      <p>
        Interrupted downloads can be retried; Ollama reuses downloaded layers.
        Download and disk errors appear here.
      </p>
    </section>
  );
}
