export const learningReferences = {
  retrieval: {
    citation:
      "Roediger & Karpicke (2006). Test-Enhanced Learning. Psychological Science, 17, 249–255.",
    url: "https://doi.org/10.1111/j.1467-9280.2006.01693.x",
  },
  explanation: {
    citation:
      "Bisra et al. (2018). Inducing Self-Explanation: a Meta-Analysis. Educational Psychology Review, 30, 703–725.",
    url: "https://doi.org/10.1007/s10648-018-9434-x",
  },
  feedback: {
    citation:
      "Hattie & Timperley (2007). The Power of Feedback. Review of Educational Research, 77, 81–112.",
    url: "https://doi.org/10.3102/003465430298487",
  },
  spacing: {
    citation:
      "Cepeda et al. (2006). Distributed Practice in Verbal Recall Tasks: A Review and Quantitative Synthesis. Psychological Bulletin, 132, 354–380.",
    url: "https://doi.org/10.1037/0033-2909.132.3.354",
  },
  interleaving: {
    citation:
      "Rohrer et al. (2020). A Randomized Controlled Trial of Interleaved Mathematics Practice. Journal of Educational Psychology, 112, 40–52.",
    url: "https://doi.org/10.1037/edu0000367",
  },
} as const;

type Principle = keyof typeof learningReferences;
export const modePrinciples = {
  single_question: ["retrieval", "explanation", "feedback"],
  random_practice: ["retrieval", "interleaving"],
  weak_topic: ["retrieval", "feedback"],
  oral_exam_simulation: ["retrieval", "explanation"],
  rapid_practice: ["retrieval", "feedback"],
  subject_simulation: ["retrieval", "explanation"],
  multi_subject: ["retrieval", "explanation"],
  full_colloquium: ["retrieval", "explanation"],
} as const satisfies Record<string, readonly Principle[]>;

export type PracticeMode = keyof typeof modePrinciples;
export const practiceModes = Object.keys(modePrinciples) as PracticeMode[];
export function isPracticeMode(mode: string): mode is PracticeMode {
  return Object.hasOwn(modePrinciples, mode);
}
