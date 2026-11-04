import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { qk } from "./hooks";
import type { JobInfo, Lecture, LectureCreated, MapDoc, SlidesDoc, SourceKind, SourceMeta } from "./types";

export const lk = {
  lecture: (c: string, l: string) => ["lecture", c, l] as const,
  map: (c: string, l: string) => ["map", c, l] as const,
  sources: (c: string) => ["sources", c] as const,
  slides: (c: string, s: string) => ["slides", c, s] as const,
};

export function thumbUrl(courseId: string, sourceId: string, slide: number): string {
  return `/api/courses/${courseId}/sources/${sourceId}/slides/${slide}/thumb`;
}

export function useLecture(courseId: string, lectureId: string, poll = false) {
  return useQuery({
    queryKey: lk.lecture(courseId, lectureId),
    queryFn: () => api<Lecture>(`/courses/${courseId}/lectures/${lectureId}`),
    refetchInterval: (q) => {
      const s = q.state.data?.map_status;
      return poll && (s === "queued" || s === "running") ? 1000 : false;
    },
  });
}

export function useMap(courseId: string, lectureId: string, enabled: boolean) {
  return useQuery({
    queryKey: lk.map(courseId, lectureId),
    queryFn: () => api<MapDoc>(`/courses/${courseId}/lectures/${lectureId}/map`),
    enabled,
    retry: false,
  });
}

export function useSources(courseId: string) {
  return useQuery({ queryKey: lk.sources(courseId), queryFn: () => api<SourceMeta[]>(`/courses/${courseId}/sources`) });
}

export function useSlides(courseId: string, sourceId: string | null) {
  return useQuery({
    queryKey: lk.slides(courseId, sourceId ?? ""),
    queryFn: () => api<SlidesDoc>(`/courses/${courseId}/sources/${sourceId}/slides`),
    enabled: Boolean(sourceId),
    staleTime: Infinity,
  });
}

function upload<T>(path: string, file: File, fields: Record<string, string> = {}): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  return api<T>(path, { method: "POST", body: fd });
}

export function useUploadLecture(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => upload<LectureCreated>(`/courses/${courseId}/lectures`, file),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.course(courseId) });
      void qc.invalidateQueries({ queryKey: lk.sources(courseId) });
    },
  });
}

export function useUploadSource(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, kind }: { file: File; kind: SourceKind }) =>
      upload<SourceMeta>(`/courses/${courseId}/sources`, file, { kind }),
    onSuccess: () => qc.invalidateQueries({ queryKey: lk.sources(courseId) }),
  });
}

export function usePatchSource(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kind }: { id: string; kind: SourceKind }) =>
      api<SourceMeta>(`/courses/${courseId}/sources/${id}`, { method: "PATCH", json: { kind } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: lk.sources(courseId) }),
  });
}

export function useDeleteSource(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/courses/${courseId}/sources/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: lk.sources(courseId) }),
  });
}

export function useReorderLectures(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (order: string[]) => api<Lecture[]>(`/courses/${courseId}/lecture-order`, { method: "PUT", json: { order } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.course(courseId) }),
  });
}

export function useRenameLecture(courseId: string, lectureId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (title: string) => api<Lecture>(`/courses/${courseId}/lectures/${lectureId}`, { method: "PATCH", json: { title } }),
    onSuccess: (l) => {
      qc.setQueryData(lk.lecture(courseId, lectureId), l);
      void qc.invalidateQueries({ queryKey: qk.course(courseId) });
    },
  });
}

export function useDeleteLecture(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (lectureId: string) => api<void>(`/courses/${courseId}/lectures/${lectureId}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.course(courseId) });
      void qc.invalidateQueries({ queryKey: lk.sources(courseId) });
    },
  });
}

export function useGenerateMap(courseId: string, lectureId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<JobInfo>(`/courses/${courseId}/lectures/${lectureId}/map/generate`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: lk.lecture(courseId, lectureId) });
      void qc.invalidateQueries({ queryKey: qk.course(courseId) });
    },
  });
}
