"""Conservative purpose checks, shared by ingestion and live evidence selection.

Original passages stay in the material/review library. These checks only keep
logistics and outline-only passages out of assessable study evidence.
"""
import re

_OVERVIEW = re.compile(r'\b(?:course (?:objectives|outline|overview)|outline of (?:the )?course|table of contents|kursziele|inhaltsverzeichnis|vorlesungsübersicht)\b', re.I)
_ADMIN = [
    r'\b(?:moodle|canvas|blackboard)\b.{0,100}\b(?:slides?|handouts?|available|download|version|folien|verfügbar)\b',
    r'\b(?:slides?|handouts?|folien)\b.{0,100}\b(?:moodle|canvas|blackboard)\b',
    r'\b(?:exercise|assignment|homework|übung\w*)\s+(?:points?|scores?|punkte\w*)\b.{0,100}\b(?:exam|klausur|prüfung)\b',
    r'\b(?:exam|klausur|prüfung)\b.{0,100}\b(?:admission|registration|eligibility|zulassung|anmeldung)\b',
    r'\b(?:office hours|submission deadline|course logistics|exam registration|exam admission|sprechstunde\w*|abgabefrist\w*|prüfungszulassung|klausurzulassung)\b',
]
_ADMIN = [re.compile(pattern, re.I) for pattern in _ADMIN]


def study_content_problem(text: str) -> str | None:
    normalized = ' '.join((text or '').split())
    if any(pattern.search(normalized) for pattern in _ADMIN):
        return 'course_administration'
    if _OVERVIEW.search(normalized[:220]) or re.match(r'^(?:learning objectives|lernziele)\s*[:\n]', (text or '').strip(), re.I):
        return 'outline_without_explanation'
    return None


def study_evidence(unit: dict) -> bool:
    return study_content_problem(unit.get('content', '')) is None
