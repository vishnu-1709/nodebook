import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { Course, CourseDetail, JobInfo, OllamaStatus, Settings } from "./types";

export const qk = {
  courses: ["courses"] as const,
  course: (id: string) => ["course", id] as const,
  settings: ["settings"] as const,
  ollama: ["ollama"] as const,
  job: (id: string) => ["job", id] as const,
};

export function useCourses() {
  return useQuery({ queryKey: qk.courses, queryFn: () => api<Course[]>("/courses") });
}

export function useCourse(id: string | undefined) {
  return useQuery({
    queryKey: qk.course(id ?? ""),
    queryFn: () => api<CourseDetail>(`/courses/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateCourse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api<Course>("/courses", { method: "POST", json: { name } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.courses }),
  });
}

export function useRenameCourse(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api<Course>(`/courses/${id}`, { method: "PATCH", json: { name } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.courses });
      void qc.invalidateQueries({ queryKey: qk.course(id) });
    },
  });
}

export function useDeleteCourse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/courses/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.courses }),
  });
}

export function useSettings() {
  return useQuery({ queryKey: qk.settings, queryFn: () => api<Settings>("/settings") });
}

export function usePatchSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<Settings>) => api<Settings>("/settings", { method: "PATCH", json: patch }),
    onSuccess: (s) => {
      qc.setQueryData(qk.settings, s);
      void qc.invalidateQueries();
    },
  });
}

export function useOllamaStatus() {
  return useQuery({
    queryKey: qk.ollama,
    queryFn: () => api<OllamaStatus>("/ollama/status"),
    refetchInterval: 30_000,
  });
}

export function useJob(id: string | null | undefined) {
  return useQuery({
    queryKey: qk.job(id ?? ""),
    queryFn: () => api<JobInfo>(`/jobs/${id}`),
    enabled: Boolean(id),
    refetchInterval: (q) => {
      const s = q.state.data?.state;
      return s === "done" || s === "failed" ? false : 700;
    },
  });
}
