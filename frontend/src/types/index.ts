export interface Exam {
  slug?: string;
  id: number;
  name: string;
  description: string;
  language: string;
  exam_duration_minutes: number;
}
export interface Job {
  id: string;
  status: string;
  message?: string;
  error?: string;
  completed?: number;
  total?: number;
  result?: unknown;
}
export interface ModelStatus {
  ollama: string;
  installed: string[];
  required: string[];
  missing: string[];
  error?: string;
}
export interface Source {
  id?: number;
  source_start?: number;
  content?: string;
  preview?: string;
  relative_path?: string;
  doc_name?: string;
  document_title?: string;
  source_location?: string;
  citation_id?: string;
}
export interface Question {
  id: number;
  question_text: string;
  review_status: string;
  enabled?: boolean;
  origin?: string;
  topic_name?: string;
  expected_core_points?: { text: string }[];
}
export interface Evaluation {
  sources?: Source[];
  subject_id?: number;
  score?: number;
  better_oral_answer?: string;
  correct?: { text?: string; claim?: string }[];
  missing?: { text?: string; claim?: string }[];
  incorrect?: { text?: string; claim?: string }[];
}
export interface Session {
  id: number;
  subject_id: number;
  status: string;
  remaining_seconds: number;
  countdown_visible: boolean;
  current_question?: Question;
  sources?: Source[];
  attempts?: {
    id: number;
    question_text: string;
    answer_text?: string;
    evaluation: Evaluation;
  }[];
  evaluation?: { percent_correct?: number; german_grade?: number };
}
export interface Run {
  id: number;
  status: string;
  mode: string;
  sessions: Session[];
  overall_evaluation?: { percent_correct?: number; german_grade?: number };
}

export interface LearningTopic {
  name: string;
  questions: number;
  available: number;
  practised: number;
  attempts: number;
  score_percent: number | null;
  mastery_state: string;
  mastery_reason: string;
}
export interface LearningData {
  goal: {
    exam_date: string | null;
    repetitions: number;
    questions_per_session: number;
  };
  topics: LearningTopic[];
  assessed_answers: number;
  streak: number;
  today_answers: number;
  activity: { date: string; answers: number }[];
  plan: {
    days_left: number | null;
    study_days: number;
    eligible_questions: number;
    total: number;
    completed: number;
    remaining: number;
    daily_questions: number;
    daily_sessions: number;
    overdue: boolean;
    schedule: { date: string; questions: number; sessions: number }[];
  };
}
