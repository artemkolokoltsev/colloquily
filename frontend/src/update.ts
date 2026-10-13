import type { Update } from "@tauri-apps/plugin-updater";

let available: Update | null = null;

export async function checkForUpdate(): Promise<Update | null> {
  if (!("__TAURI_INTERNALS__" in window)) return null;
  const { check } = await import("@tauri-apps/plugin-updater");
  available = await check();
  return available;
}

export function pendingUpdate() { return available; }

export async function installPendingUpdate(onProgress: (value: number | null) => void) {
  if (!available) return;
  let downloaded = 0;
  let total = 0;
  await available.downloadAndInstall((event) => {
    if (event.event === "Started") total = event.data.contentLength ?? 0;
    if (event.event === "Progress") downloaded += event.data.chunkLength;
    onProgress(total ? Math.round(downloaded / total * 100) : null);
  });
  const { relaunch } = await import("@tauri-apps/plugin-process");
  await relaunch();
}
