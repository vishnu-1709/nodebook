// Mirrors backend/core/schemas.py. Keep in sync.

export type Status = "not_started" | "confused" | "revising" | "got_it";
export const STATUS_LABEL: Record<Status, string> = {
  not_started: "Not started",
  confused: "Confused",
  revising: "Revising",
  got_it: "Got it",
};

export interface SlideRef {
  source_id: string;
  slide: number;
}

export interface Course {
  id: string;
  name: string;
  lecture_order: string[];
  created_at: string;
}

export type MapStatus = "none" | "queued" | "running" | "ready" | "failed";

export interface Lecture {
  id: string;
  course_id: string;
  title: string;
  order: number;
  source_ids: string[];
  map_status: MapStatus;
  map_job_id: string | null;
  map_error: string | null;
  map_fallback: boolean;
  uncovered_slides: SlideRef[];
  created_at: string;
}

export interface CourseDetail {
  course: Course;
  lectures: Lecture[];
}

export interface PomodoroPreset {
  work_min: number;
  break_min: number;
}

export type Theme = "system" | "light" | "dark";

export interface Settings {
  data_dir: string;
  onboarded: boolean;
  theme: Theme;
  ollama_url: string;
  provider: string;
  map_model: string | null;
  study_model: string | null;
  keep_all_questions: boolean;
  usage_log: boolean;
  pomodoro_presets: PomodoroPreset[];
}

export interface ModelInfo {
  name: string;
  size_bytes: number;
  parameter_size: string;
  family: string;
  vision: boolean;
}

export interface OllamaStatus {
  status: { reachable: boolean; version: string; url: string; error: string };
  models: ModelInfo[];
  models_error: string;
  json_warnings: string[];
}

export type JobState = "queued" | "running" | "done" | "failed";

export interface JobInfo {
  id: string;
  kind: string;
  state: JobState;
  step: string;
  progress: number;
  message: string;
  error: string | null;
  result: Record<string, unknown> | null;
}
