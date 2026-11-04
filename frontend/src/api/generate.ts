import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { NoteDestination } from "./notes";
import type { GradeResult } from "./testme";
import type { SlideRef } from "./types";

export type GenType = "questions" | "flashcards" | "summary" | "explain";
export type Chip = "harder" | "easier" | "conceptual" | "numerical";

export interface GeneratedItem {
  type: GenType;
  front: string;
  back: string;
  title: string;
  body: string;
  sources: SlideRef[];
  source_ids: string[];
  ref: string;
  key: string;
  suggested: NoteDestination | null;
}

export interface GenRequest {
  type: GenType;
  source_ids: string[];
  lecture_ids: string[];
  steer: string;
  chips: Chip[];
  topic: string;
  exclude: string[];
}

export function useGenerate(courseId: string) {
  const qc = useQueryClient();
  const base = `/courses/${courseId}/generate`;
  return {
    generate: useMutation({ mutationFn: (r: GenRequest) => api<GeneratedItem>(base, { method: "POST", json: r }) }),
    check: useMutation({
      mutationFn: (b: { question: string; reference: string; answer: string; sources: SlideRef[] }) =>
        api<GradeResult>(`${base}/check`, { method: "POST", json: b }),
    }),
    save: useMutation({
      mutationFn: (b: { item: GeneratedItem; destination: NoteDestination }) =>
        api<{ kind: string; lecture_id: string | null; node_id: string | null; id: string }>(`${base}/save`, { method: "POST", json: b }),
      onSuccess: () => {
        void qc.invalidateQueries({ queryKey: ["practice"] });
        void qc.invalidateQueries({ queryKey: ["notes"] });
        void qc.invalidateQueries({ queryKey: ["thread"] });
        void qc.invalidateQueries({ queryKey: ["kept-counts"] });
      },
    }),
  };
}

export function useGenDestinations(courseId: string | null) {
  return useQuery({
    queryKey: ["gen-dests", courseId],
    queryFn: () => api<NoteDestination[]>(`/courses/${courseId}/generate/destinations`),
    enabled: Boolean(courseId),
  });
}
