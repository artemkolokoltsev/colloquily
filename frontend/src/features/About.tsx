import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
export function About({
  open,
  close,
  version,
}: {
  open: boolean;
  close: () => void;
  version: string;
}) {
  const { t } = useTranslation();
  const dialog = useRef<HTMLDialogElement>(null);
  const [path, setPath] = useState("");
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);
  useEffect(() => {
    if (open)
      void api<{ data_directory: string }>("/settings")
        .then((value) => setPath(value.data_directory))
        .catch(() => undefined);
  }, [open]);
  return (
    <dialog
      ref={dialog}
      className="about-dialog"
      aria-labelledby="about-title"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
    >
      <header className="dialog-toolbar">
        <h2 id="about-title">{t("ui.aboutTitle")}</h2>
        <button onClick={close} aria-label={t("ui.aboutClose")}>
          ×
        </button>
      </header>
      <div className="about-brand">
        <img src="/favicon.svg" alt="" width="64" height="64" />
        <div>
          <strong>Colloquily</strong>
          <p>{t("settings.currentVersion", { version })}</p>
        </div>
      </div>
      <p>{t("ui.aboutPurpose")}</p>
      <div id="about-updates" />
      <section>
        <h3>{t("ui.aboutLocalTitle")}</h3>
        <p>{t("ui.aboutLocal")}</p>
      </section>
      <section>
        <h3>{t("ui.aboutFeedbackTitle")}</h3>
        <p>{t("ui.aboutFeedback")}</p>
      </section>
      <details>
        <summary>{t("ui.aboutDetails")}</summary>
        <dl>
          <dt>{t("ui.aboutPlatform")}</dt>
          <dd>{navigator.platform}</dd>
          <dt>{t("ui.aboutStorage")}</dt>
          <dd className="storage-path">{path || "…"}</dd>
          <dt>{t("ui.aboutLicense")}</dt>
          <dd>Apache-2.0</dd>
        </dl>
      </details>
      <small>
        © {new Date().getFullYear()} Colloquily. {t("ui.rightsReserved")}
      </small>
    </dialog>
  );
}
