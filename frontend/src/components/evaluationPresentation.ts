import type { Evaluation } from "../types/index.ts";
const normalized = (value: string) =>
  value
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/\s+/gu, " ")
    .replace(/[.!?]+$/u, "")
    .trim();
export function evaluationPresentation(value: Evaluation) {
  const seen = new Set<string>();
  const unique = (points: { text?: string; claim?: string }[] = []) =>
    points
      .map((point) => (point.text || point.claim || "").trim())
      .filter((text) => {
        const key = normalized(text);
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  const incorrect = unique(value.incorrect),
    missing = unique(value.missing),
    correct = unique(value.correct);
  const expected = unique(value.expected_core_points);
  const modelAnswer = (value.better_oral_answer || "").trim();
  const combined = normalized(
    [...incorrect, ...missing, ...correct, ...expected].join(" "),
  );
  return {
    incorrect,
    missing,
    correct,
    expected,
    modelAnswer:
      seen.has(normalized(modelAnswer)) || normalized(modelAnswer) === combined
        ? ""
        : modelAnswer,
  };
}
