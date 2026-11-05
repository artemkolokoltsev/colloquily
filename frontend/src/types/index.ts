export interface Exam {
  slug?: string;
  id: number;
  name: string;
  description: string;
  language: string;
  exam_duration_minutes: number;
}
export interface Job {
  phase?: string;
  candidates?: number;
  accepted?: number;
  rejected?: number;
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
  status?: string;
  expected_core_points?: { text: string }[];
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
  evaluation_status?: string;
  evaluation_job?: Job;
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
  average_score: number | null;
  practised_questions: number;
  goal: {
    exam_date: string | null;
    repetitions: number;
    questions_per_session: number;
  };
  topics: LearningTopic[];
  assessed_answers: number;
  streak: number;
  today_answers: number;
  today_target: number;
  today_completed: number;
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

export interface LectureScript {
  document_id: number;
  revision: number;
  filename: string;
  relative_path: string;
}
export interface MaterialUnit {
  id: number;
  document_id: number;
  content: string;
  review_status: string;
  document_title: string;
  relative_path: string;
  source_location: string;
  source_start?: number;
  quality_problems?: string[];
  study_problem?: string | null;
}
export interface MaterialReviewPage {
  items: MaterialUnit[];
  total: number;
  offset: number;
  limit: number;
}
export interface SubmissionProfile {
  course_name: string;
  semester: string;
  authors: { name: string; matrikelnummer: string }[];
}
export interface ExerciseSheet {
  id: number;
  title: string;
  filename: string;
  pages: number;
  revision: number;
  updated_at: string;
  latex: string;
}
