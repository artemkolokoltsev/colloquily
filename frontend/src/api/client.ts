import type { Job } from "../types";
import i18n from "../i18n";
let base = "";
let token = "";
export async function connect() {
  if ("__TAURI_INTERNALS__" in window) {
    const { invoke } = await import("@tauri-apps/api/core");
    const info = await invoke<{ url: string; token: string }>(
      "backend_connection",
    );
    base = info.url;
    token = info.token;
  }
  await api("/health");
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  headers["Accept-Language"] = i18n.resolvedLanguage || "en";
  if (token) headers["X-Colloquily-Token"] = token;
  if (body !== undefined && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  const response = await fetch(`${base}/api${path}`, {
    method,
    headers,
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    const code = error.error?.code;
    const translated = code && i18n.exists(`errors.${code}`) ? i18n.t(`errors.${code}`, { defaultValue: i18n.t('errors.unknown') }) : undefined;
    throw new Error(translated || error.error?.message || (typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail)));
  }
  return response.json();
}
export async function operation<T>(
  path: string,
  body: unknown,
  update: (job: Job) => void,
): Promise<T> {
  let job = await api<Job>(path, "POST", body);
  update(job);
  while (job.status === "queued" || job.status === "running") {
    await new Promise((resolve) => setTimeout(resolve, 700));
    job = await api<Job>(`/jobs/${job.id}`);
    update(job);
  }
  if (job.status !== "completed")
    throw new Error(job.error || i18n.t("common.operationFailed"));
  return job.result as T;
}
export async function sourceBlob(exam: number, filename: string) {
  const response = await fetch(
    `${base}/api/exams/${exam}/sources/${filename.split("/").map(encodeURIComponent).join("/")}`,
    { headers: token ? { "X-Colloquily-Token": token } : {} },
  );
  if (!response.ok) throw new Error("Unable to open source");
  return URL.createObjectURL(await response.blob());
}

export async function downloadBackup(filename: string) {
  const response = await fetch(`${base}/api/backups/${encodeURIComponent(filename)}`, { headers: token ? { 'X-Colloquily-Token': token } : {} });
  if (!response.ok) throw new Error(i18n.t('errors.unknown'));
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
