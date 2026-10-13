import { useTranslation } from "react-i18next";
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
  const { t: tr } = useTranslation();
  return (
    <div className="learning-map">
      <div className="map-root">
        <span className="brand-mini">{tr('ui.s6b23c0d5f3')}</span>
        <strong>{tr('ui.scbbacdb84b')}</strong>
        <small>{tr('ui.sb68e9b41d7')}</small>
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
              {t.practised}/{t.questions} {tr('ui.sb77d660174')} {t.attempts}{" "} {tr('ui.s677fe21b65')} </small>
          </button>
        ))}
      </div>
      {!topics.length && (
        <p className="empty-state"> {tr('ui.s5c8a74fe01')} </p>
      )}
      <p className="map-caption"> {tr('ui.s6510c73809')} </p>
    </div>
  );
}
