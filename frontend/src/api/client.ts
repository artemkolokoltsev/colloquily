import type { Job } from "../types";
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
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
    );
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
    throw new Error(job.error || "Operation failed");
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
