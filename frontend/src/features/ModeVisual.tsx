import type { PracticeMode } from "./practiceLearning";

// Small diagrams communicate the structure of a session without extra navigation.
export function ModeVisual({ mode }: { mode: PracticeMode }) {
  const drawings = {
    single_question: (
      <>
        <rect x="52" y="20" width="56" height="64" rx="12" />
        <path d="M67 39h26M67 49h18M72 65l6 6 13-14" />
      </>
    ),
    random_practice: (
      <>
        <path d="M28 32h22c25 0 35 40 60 40h22M28 72h22c25 0 35-40 60-40h22M122 22l10 10-10 10M122 62l10 10-10 10" />
        <circle cx="28" cy="32" r="5" />
        <circle cx="28" cy="72" r="5" />
      </>
    ),
    weak_topic: (
      <>
        <circle cx="80" cy="52" r="34" />
        <circle cx="80" cy="52" r="22" />
        <circle cx="80" cy="52" r="8" />
        <path d="M80 52l39-35M105 17h14v14" />
      </>
    ),
    oral_exam_simulation: (
      <>
        <rect x="68" y="20" width="24" height="42" rx="12" />
        <path d="M56 49v5a24 24 0 0048 0v-5M80 78v12M67 90h26M35 39v23M125 39v23" />
      </>
    ),
    rapid_practice: (
      <>
        <path d="M88 15L51 58h25l-7 32 40-48H83z" />
        <path d="M31 34h20M22 48h19M30 64h14M116 74h17" />
      </>
    ),
    subject_simulation: (
      <>
        <path d="M32 27c20-7 36-3 48 7 12-10 28-14 48-7v53c-20-7-36-3-48 7-12-10-28-14-48-7zM80 34v53M45 42l21 4M45 55l21 4M94 46l21-4M94 59l21-4" />
      </>
    ),
    multi_subject: (
      <>
        <circle cx="43" cy="52" r="22" />
        <circle cx="117" cy="52" r="22" />
        <path d="M68 42h25l-7-7M93 62H68l7 7" />
        <path d="M36 52h14M43 45v14M111 48h12M111 56h12" />
      </>
    ),
    full_colloquium: (
      <>
        <rect x="20" y="43" width="30" height="41" rx="6" />
        <rect x="65" y="20" width="30" height="64" rx="6" />
        <rect x="110" y="34" width="30" height="50" rx="6" />
        <path d="M29 57h12M74 35h12M119 49h12M20 94h120" />
      </>
    ),
  };
  return (
    <svg
      className={`mode-visual mode-visual-${mode}`}
      viewBox="0 0 160 108"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {drawings[mode]}
    </svg>
  );
}
