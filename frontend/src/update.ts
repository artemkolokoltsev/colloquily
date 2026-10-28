import { api } from './api/client';
import { UpdateController } from './updateController';

export const updater = new UpdateController({
  check: async () => {
    if (!("__TAURI_INTERNALS__" in window)) return null;
    const { check } = await import('@tauri-apps/plugin-updater');
    return check({timeout: 20000});
  },
  safe: async () => (await api<{safe: boolean}>('/system/activity')).safe,
  begin: () => api('/system/update/begin', 'POST', {}),
  cancel: () => api('/system/update/cancel', 'POST', {}),
  relaunch: async () => { const { relaunch } = await import('@tauri-apps/plugin-process'); await relaunch(); },
});
export const checkForUpdate = () => updater.check();
