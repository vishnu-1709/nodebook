import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

export interface ReminderLink {
  kind: "course" | "lecture" | "node";
  id: string;
  course_id: string | null;
  lecture_id: string | null;
}

export interface Reminder {
  id: string;
  text: string;
  due_at: string;
  tags: string[];
  course_id: string | null;
  link: ReminderLink | null;
  done: boolean;
}

export interface TagColour {
  name: string;
  colour: string;
}

export interface Parsed {
  text: string;
  due_at: string | null;
  tags: string[];
  matched: string;
}

export interface TodayData {
  has_courses: boolean;
  current_course_id: string | null;
  weak_nodes: { course_id: string; course_name: string; lecture_id: string; lecture_title: string; node_id: string; label: string }[];
  progress: { course_id: string; course_name: string; lecture_id: string; title: string; got_it: number; revising: number; confused: number; not_started: number }[];
  overdue: Reminder[];
  today: Reminder[];
  upcoming: Reminder[];
  exam: { reminder: Reminder; days: number } | null;
}

export function useToday() {
  return useQuery({ queryKey: ["today"], queryFn: () => api<TodayData>("/today"), refetchInterval: 60_000 });
}

export function useReminders() {
  return useQuery({
    queryKey: ["reminders"],
    queryFn: () => api<{ items: Reminder[]; custom_tags: TagColour[]; builtin_tags: string[] }>("/reminders"),
  });
}

export function useReminderMutations() {
  const qc = useQueryClient();
  const done = () => {
    void qc.invalidateQueries({ queryKey: ["reminders"] });
    void qc.invalidateQueries({ queryKey: ["today"] });
  };
  return {
    create: useMutation({
      mutationFn: (b: { text: string; due_at: string; tags: string[]; link: ReminderLink | null; course_id: string | null }) =>
        api<Reminder>("/reminders", { method: "POST", json: b }),
      onSuccess: done,
    }),
    patch: useMutation({
      mutationFn: ({ id, ...b }: { id: string; done?: boolean; text?: string; due_at?: string; tags?: string[] }) =>
        api<Reminder>(`/reminders/${id}`, { method: "PATCH", json: b }),
      onSuccess: done,
    }),
    remove: useMutation({ mutationFn: (id: string) => api<void>(`/reminders/${id}`, { method: "DELETE" }), onSuccess: done }),
  };
}

export function parseReminder(text: string): Promise<Parsed> {
  return api<Parsed>("/reminders/parse", { method: "POST", json: { text } });
}

/** "in 3 days", "today 17:00", "2 days ago" — calm, relative. */
export function relativeDue(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(d) - day(now)) / 86_400_000);
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  if (diff === 0) return `today ${time}`;
  if (diff === 1) return `tomorrow ${time}`;
  if (diff === -1) return "yesterday";
  if (diff < 0) return `${-diff} days ago`;
  if (diff < 7) return `${d.toLocaleDateString(undefined, { weekday: "short" })} ${time}`;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export const BUILTIN_TAG_COLOUR: Record<string, string> = {
  exam: "tag-3", assignment: "tag-1", lab: "tag-2", quiz: "tag-4", revise: "tag-5",
};
