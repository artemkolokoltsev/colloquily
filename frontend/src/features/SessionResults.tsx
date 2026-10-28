import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Exam, Run } from "../types";
import { EvaluationView } from "../components/Common";
import { StudyText } from "../components/StudyText";
import { analyseSession } from "./sessionAnalysis";

export function SessionResults({ run, exams }: { run: Run; exams: Exam[] }) {
  const { t } = useTranslation();
  const data = analyseSession(run);
  const [chosen, setChosen] = useState<number>();
  const selected =
    data.attempts.find((attempt) => attempt.id === chosen) ||
    data.improvements[0] ||
    data.attempts[0];
  const selectedIndex = data.attempts.findIndex(
    (attempt) => attempt.id === selected?.id,
  );
  const pending = ["waiting", "queued", "running"].includes(
    run.evaluation_status || "",
  );
  return (
    <section className="session-analysis" aria-label={t("ui.resultsAnalysis")}>
      <h3>{t("ui.resultsAnalysis")}</h3>
      <div className="result-stats">
        <div>
          <strong>{data.graded.length}</strong>
          <span>{t("ui.resultsGraded")}</span>
        </div>
        <div>
          <strong>{data.skipped}</strong>
          <span>{t("ui.resultsSkipped")}</span>
        </div>
        <div>
          <strong>{data.ungraded}</strong>
          <span>{t("ui.resultsUngraded")}</span>
        </div>
        <div>
          <strong>
            {data.mean === null ? "—" : `${data.mean.toFixed(1)} / 5`}
          </strong>
          <span>{t("ui.resultsAverage")}</span>
        </div>
      </div>
      {!pending && run.overall_evaluation?.german_grade != null && (
        <p>
          {t("ui.resultsGrade", { grade: run.overall_evaluation.german_grade })}
        </p>
      )}
      {!!data.skipped && <p className="muted">{t("ui.resultsSkipNote")}</p>}
      {!!data.ungraded && (
        <p className="muted">{t("ui.resultsUngradedNote")}</p>
      )}
      {data.attempts.length ? (
        <>
          <h4>{t("ui.resultsChart")}</h4>
          <p className="muted">{t("ui.resultsChartHint")}</p>
          <div
            className="result-chart"
            role="group"
            aria-label={t("ui.resultsChart")}
          >
            {data.attempts.map((attempt, i) => {
              const graded = data.graded.some((item) => item.id === attempt.id);
              const score = graded ? attempt.evaluation.score! : null;
              const status =
                score === null
                  ? t(
                      attempt.evaluation.status === "skipped"
                        ? "ui.resultsSkipped"
                        : "ui.resultsUngraded",
                    )
                  : `${score}/5`;
              return (
                <button
                  key={attempt.id}
                  className="result-chart-row"
                  aria-pressed={selected?.id === attempt.id}
                  aria-label={`${i + 1}. ${attempt.question_text} · ${status}`}
                  onClick={() => setChosen(attempt.id)}
                >
                  <span>{i + 1}</span>
                  <span
                    className={`result-track ${score === null ? "ungraded" : ""}`}
                  >
                    <span
                      style={{ width: `${score === null ? 0 : score * 20}%` }}
                    />
                  </span>
                  <strong>{status}</strong>
                </button>
              );
            })}
          </div>
          <h4>{t("ui.resultsNext")}</h4>
          {pending ? (
            <p>{t("ui.autoEvaluating")}</p>
          ) : data.improvements.length ? (
            <ol className="result-actions">
              {data.improvements.map((attempt) => (
                <li key={attempt.id}>
                  <button onClick={() => setChosen(attempt.id)}>
                    {attempt.question_text}
                  </button>
                  <p>
                    {t(
                      attempt.evaluation.incorrect?.length
                        ? "ui.resultsCorrect"
                        : "ui.resultsRecall",
                    )}
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <p>
              {t(data.graded.length ? "ui.resultsMaintain" : "ui.resultsStart")}
            </p>
          )}
          {selected && (
            <article
              className="result-detail"
              aria-label={t("ui.resultsDetail")}
            >
              <p className="eyebrow">
                {exams.find((exam) => exam.id === selected.subjectId)?.name}
              </p>
              <h4>{selected.question_text}</h4>
              <nav
                className="answer-review-nav"
                aria-label={t("ui.feedbackNavigation")}
              >
                <button
                  disabled={selectedIndex <= 0}
                  onClick={() => setChosen(data.attempts[selectedIndex - 1].id)}
                >
                  {t("ui.feedbackPrevious")}
                </button>
                <span>
                  {selectedIndex + 1} / {data.attempts.length}
                </span>
                <button
                  disabled={selectedIndex >= data.attempts.length - 1}
                  onClick={() => setChosen(data.attempts[selectedIndex + 1].id)}
                >
                  {t("ui.feedbackNext")}
                </button>
              </nav>
              <EvaluationView
                value={selected.evaluation}
                answer={selected.answer_text || ""}
              />
            </article>
          )}
        </>
      ) : (
        <p>{t("ui.resultsStart")}</p>
      )}
    </section>
  );
}
