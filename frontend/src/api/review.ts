import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { PracticeItem } from "./types";

export interface ReviewItem {
  item: PracticeItem;
  course_id: string;
  lecture_id: string | null;
  lecture_title: string;
  node_label: string;
  node_path: string[];
  node_status: string;
  intervals: Record<"1" | "2" | "3" | "4", string>;
}

export function useReviewQueue(courseId: string | null, lectureId: string | null, enabled = true) {
  const qs = new URLSearchParams();
  if (courseId) qs.set("course_id", courseId);
  if (lectureId) qs.set("lecture_id", lectureId);
  return useQuery({
    queryKey: ["review-queue", courseId, lectureId],
    queryFn: () => api<{ items: ReviewItem[]; total: number }>(`/review/queue?${qs.toString()}`),
    enabled,
    staleTime: Infinity, // a session works on a snapshot
  });
}

export function useDueCounts() {
  return useQuery({
    queryKey: ["due-counts"],
    queryFn: () => api<{ total: number; by_course: Record<string, number> }>("/review/counts"),
    refetchInterval: 60_000,
  });
}

export function useRate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { course_id: string; lecture_id: string | null; item_id: string; rating: 1 | 2 | 3 | 4; duration_ms?: number }) =>
      api<{ item: PracticeItem; remaining: number }>("/review/rate", { method: "POST", json: b }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["due-counts"] });
      void qc.invalidateQueries({ queryKey: ["practice"] });
    },
  });
}

export function minutesFor(n: number): number {
  return Math.max(1, Math.round((n * 30) / 60)); // ~30 s per item
}
