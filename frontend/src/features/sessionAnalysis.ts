import type { Run } from "../types/index.ts";

export function analyseSession(run: Run) {
  const attempts = run.sessions.flatMap((session) =>
    (session.attempts || []).map((attempt) => ({
      ...attempt,
      subjectId: session.subject_id,
    })),
  );
  const graded = attempts.filter((attempt) => {
    const evaluation = attempt.evaluation;
    return (
      !["skipped", "pending", "needs_review", "internal_error"].includes(
        evaluation.status || "",
      ) &&
      typeof evaluation.score === "number" &&
      Number.isFinite(evaluation.score) &&
      evaluation.score >= 0 &&
      evaluation.score <= 5
    );
  });
  const skipped = attempts.filter(
    (attempt) => attempt.evaluation.status === "skipped",
  ).length;
  const mean = graded.length
    ? graded.reduce((sum, attempt) => sum + attempt.evaluation.score!, 0) /
      graded.length
    : null;
  const improvements = [...graded]
    .filter(
      (attempt) =>
        attempt.evaluation.score! < 4 ||
        attempt.evaluation.missing?.length ||
        attempt.evaluation.incorrect?.length,
    )
    .sort((a, b) => a.evaluation.score! - b.evaluation.score!)
    .slice(0, 3);
  return {
    attempts,
    graded,
    skipped,
    ungraded: attempts.length - graded.length - skipped,
    mean,
    improvements,
  };
}
