import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorNotice } from "../components/Common";
import {
  isPracticeMode,
  learningReferences,
  modePrinciples,
} from "./practiceLearning";

export function PracticeGuide({
  mode,
  compact = false,
}: {
  mode: string;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const [error, setError] = useState("");
  if (!isPracticeMode(mode)) return null;
  const principles = [...modePrinciples[mode], "spacing"] as const;
  const content = (
    <>
      <h3 id="practice-guide-title">{t(`dynamic.${mode}`)}</h3>
      <dl className="practice-guide-grid">
        {(["goal", "method", "format"] as const).map((field) => (
          <div key={field}>
            <dt>{t(`practiceLearning.${field}Label`)}</dt>
            <dd>{t(`practiceLearning.${mode}_${field}`)}</dd>
          </div>
        ))}
      </dl>
      <p className="muted practice-timing">
        {t("practiceLearning.timingNote")}
      </p>
      <p className="practice-reflection">{t("practiceLearning.spacingTip")}</p>
      <details className="practice-research">
        <summary>{t("practiceLearning.researchLabel")}</summary>
        <p className="muted">{t("practiceLearning.evidenceScope")}</p>
        <ErrorNotice error={error} />
        {principles.map((principle) => {
          const reference = learningReferences[principle];
          return (
            <div className="learning-principle" key={principle}>
              <h4>{t(`practiceLearning.${principle}_title`)}</h4>
              <p>{t(`practiceLearning.${principle}_text`)}</p>
              <a
                href={reference.url}
                target="_blank"
                rel="noreferrer"
                onClick={async (event) => {
                  if (!("__TAURI_INTERNALS__" in window)) return;
                  event.preventDefault();
                  setError("");
                  try {
                    const { invoke } = await import("@tauri-apps/api/core");
                    await invoke("open_learning_reference", {
                      reference: principle,
                    });
                  } catch {
                    setError(t("practiceLearning.openReferenceError"));
                  }
                }}
              >
                {reference.citation}
              </a>
            </div>
          );
        })}
      </details>
    </>
  );
  return compact ? (
    <details className="practice-guide">
      <summary>{t("practiceLearning.guideTitle")}</summary>
      {content}
    </details>
  ) : (
    <article
      id="practice-mode-guide"
      className="practice-guide"
      aria-labelledby="practice-guide-title"
    >
      <p className="eyebrow">{t("practiceLearning.guideTitle")}</p>
      {content}
    </article>
  );
}
