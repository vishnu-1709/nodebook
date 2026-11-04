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
  map_warnings: string[];
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

export type SourceKind = "slides" | "pyq" | "notes" | "textbook" | "other";
export const SOURCE_KIND_LABEL: Record<SourceKind, string> = {
  slides: "Slides",
  pyq: "Past paper",
  notes: "Notes",
  textbook: "Textbook",
  other: "Other",
};

export interface SourceMeta {
  id: string;
  filename: string;
  ext: string;
  kind: SourceKind;
  size: number;
  lecture_id: string | null;
  slide_count: number | null;
  has_thumbnails: boolean;
  added_at: string;
}

export interface MapNode {
  id: string;
  label: string;
  parent_id: string | null;
  children: string[];
  sources: SlideRef[];
  status: Status;
  status_mode: "manual" | "auto";
  last_studied_at: string | null;
  origin: "ai" | "user";
  collapsed: boolean;
}

export interface MapDoc {
  lecture_id: string;
  root_id: string;
  nodes: Record<string, MapNode>;
}

export interface Slide {
  number: number;
  text: string;
  has_images: boolean;
}

export interface SlidesDoc {
  source_id: string;
  slides: Slide[];
}

export interface LectureCreated {
  lecture: Lecture;
  job: JobInfo;
}

export type MessageKind = "question" | "try_first" | "attempt" | "answer" | "hint";

export interface Message {
  role: "user" | "assistant";
  kind: MessageKind;
  content: string;
}

export interface Exchange {
  id: string;
  kept_at: string | null;
  created_at: string;
  messages: Message[];
  node_id?: string;
  expires_at?: string;
}

export interface NodeThread {
  kept: Exchange[];
  recent: Exchange[];
}

export interface PracticeItem {
  id: string;
  type: "card" | "question";
  node_id: string | null;
  front: string;
  back: string;
  answer_status: "ai_unverified" | "verified";
  origin: { kind: string; source_ids: string[]; ref: string };
  fsrs: Record<string, unknown> | null;
  created_at: string;
}

export interface Note {
  id: string;
  text: string;
  node_id: string | null;
  pinned_from: string | null;
  created_at: string;
  updated_at: string;
}
