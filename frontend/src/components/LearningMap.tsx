import type { LearningTopic } from "../types";
export function LearningMap({
  topics,
  selected,
  onSelect,
}: {
  topics: LearningTopic[];
  selected: string;
  onSelect: (name: string) => void;
}) {
  return (
    <div className="learning-map">
      <div className="map-root">
        <span className="brand-mini">C</span>
        <strong>Your knowledge map</strong>
        <small>Select a topic to explore its questions</small>
      </div>
      <div className="map-branches">
        {topics.map((t) => (
          <button
            key={t.name}
            className={`topic-node ${t.mastery_state} ${selected === t.name ? "selected" : ""}`}
            aria-pressed={selected === t.name}
            onClick={() => onSelect(selected === t.name ? "" : t.name)}
          >
            <span className="node-heading">
              <strong>{t.name}</strong>
              <span
                className="score-ring"
                style={
                  {
                    "--score": `${t.score_percent ?? 0}%`,
                  } as React.CSSProperties
                }
              >
                {t.score_percent === null ? "—" : `${t.score_percent}%`}
              </span>
            </span>
            <span className="status-label">
              {t.mastery_state.replaceAll("_", " ")}
            </span>
            <small>
              {t.practised}/{t.questions} questions practised · {t.attempts}{" "}
              answers
            </small>
          </button>
        ))}
      </div>
      {!topics.length && (
        <p className="empty-state">
          Import or generate questions to grow your topic map.
        </p>
      )}
      <p className="map-caption">
        Branches group questions by topic. Rings show average assessed scores;
        they are not a guarantee of exam readiness.
      </p>
    </div>
  );
}
