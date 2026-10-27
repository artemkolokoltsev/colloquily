import { useEffect, useState, useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";
import { createPortal } from "react-dom";
import { updater } from "../update";

export function UpdateNotice({
  home,
  visible = false,
}: {
  home: boolean;
  visible?: boolean;
}) {
  const { t } = useTranslation();
  const state = useSyncExternalStore(updater.subscribe, updater.snapshot);
  const [automatic, setAutomatic] = useState(
    () => localStorage.getItem("colloquily.autoUpdates") !== "false",
  );
  const [countdown, setCountdown] = useState<number | null>(null);
  const [deferred, setDeferred] = useState(false);
  useEffect(() => {
    if (!("__TAURI_INTERNALS__" in window)) return;
    setCountdown(null);
    let stopped = false,
      checking = false,
      nextCheck = 0,
      idleSince = Date.now(),
      deadline = 0;
    const editable = () =>
      !!document.querySelector("[data-update-blocked=true]") ||
      [
        ...document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(
          "main input:not([type=checkbox]):not([type=radio]), main textarea, main [contenteditable=true]",
        ),
      ].some(
        (input) => input.type !== "hidden" && input.getClientRects().length > 0,
      );
    const active = () => {
      idleSince = Date.now();
      deadline = 0;
      setCountdown(null);
    };
    const online = () => {
      nextCheck = 0;
      void tick();
    };
    const tick = async () => {
      if (stopped || checking || !automatic || !navigator.onLine) return;
      checking = true;
      try {
        if (Date.now() >= nextCheck) {
          nextCheck = Date.now() + 6 * 60 * 60 * 1000;
          await updater.check();
          if (stopped) return;
          await updater.download();
        }
        // Only the home screen can restart unattended; forms and practice stay open.
        if (
          !stopped &&
          home &&
          !editable() &&
          !deferred &&
          updater.state.phase === "ready" &&
          Date.now() - idleSince >= 120000
        ) {
          if (!deadline) deadline = Date.now() + 30000;
          setCountdown(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
          if (Date.now() >= deadline) {
            deadline = 0;
            idleSince = Date.now();
            await updater.install();
          }
        }
      } catch {
        nextCheck = Date.now() + 15 * 60 * 1000;
      } finally {
        checking = false;
      }
    };
    window.addEventListener("online", online);
    window.addEventListener("pointerdown", active);
    window.addEventListener("keydown", active);
    window.addEventListener("wheel", active, { passive: true });
    window.addEventListener("touchmove", active, { passive: true });
    const timer = window.setInterval(() => void tick(), 1000);
    void tick();
    return () => {
      stopped = true;
      window.clearInterval(timer);
      window.removeEventListener("online", online);
      window.removeEventListener("pointerdown", active);
      window.removeEventListener("keydown", active);
      window.removeEventListener("wheel", active);
      window.removeEventListener("touchmove", active);
    };
  }, [automatic, home, deferred]);
  if (!("__TAURI_INTERNALS__" in window)) return null;
  const busy = ["checking", "downloading", "installing", "restarting"].includes(
    state.phase,
  );
  if (!visible)
    return countdown !== null ? (
      <div className="update-toast" role="status">
        {t("updates.countdown", { count: countdown })}
        <button
          onClick={() => {
            setDeferred(true);
            setCountdown(null);
          }}
        >
          {t("updates.later")}
        </button>
      </div>
    ) : null;
  const target = document.getElementById("about-updates");
  if (!target) return null;
  return createPortal(
    <section className="update-notice">
      <h3>
        {t("updates.title")}
        {state.version ? ` · ${state.version}` : ""}
      </h3>
      <p role="status">{t(`updates.${state.phase}`)}</p>
      <label>
        <input
          type="checkbox"
          checked={automatic}
          onChange={(event) => {
            setAutomatic(event.target.checked);
            setCountdown(null);
            localStorage.setItem(
              "colloquily.autoUpdates",
              String(event.target.checked),
            );
          }}
        />
        {t("updates.automatic")}
      </label>
      <p className="muted">{t("updates.behavior")}</p>
      {state.phase === "downloading" && (
        <progress
          aria-label={t("updates.downloading")}
          max={100}
          value={state.progress}
        />
      )}
      {state.notes && (
        <details>
          <summary>{t("release.notes")}</summary>
          <p className="prose">{state.notes}</p>
        </details>
      )}
      {countdown !== null && (
        <p role="status">{t("updates.countdown", { count: countdown })}</p>
      )}
      <div className="actions">
        <button
          disabled={busy}
          onClick={() => void updater.check().catch(() => undefined)}
        >
          {t("settings.checkUpdates")}
        </button>
        {state.version && (
          <button
            disabled={busy}
            onClick={() => {
              setCountdown(null);
              void updater.install().catch(() => undefined);
            }}
          >
            {t("settings.installUpdate")}
          </button>
        )}
        {state.version && (
          <button
            disabled={
              state.phase === "installing" || state.phase === "restarting"
            }
            onClick={() => {
              setDeferred(true);
              setCountdown(null);
            }}
          >
            {t("updates.later")}
          </button>
        )}
      </div>
      {deferred && <p>{t("updates.deferred")}</p>}
    </section>,
    target,
  );
}
