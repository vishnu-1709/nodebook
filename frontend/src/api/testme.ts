import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { PracticeItem, SlideRef } from "./types";

export interface TestQuestion {
  id: string;
  question: string;
  source: SlideRef | null;
}

export type Verdict = "correct" | "partly" | "wrong";

export interface GradeResult {
  question: string;
  answer: string;
  verdict: Verdict;
  feedback: string;
  source: SlideRef | null;
}

export interface ResultRecord {
  id: string;
  node_id: string;
  kind: "test_me" | "recall" | "explain";
  score: number;
  details: { items?: GradeResult[] } & Record<string, unknown>;
  created_at: string;
}

const base = (c: string, l: string, n: string) => `/courses/${c}/lectures/${l}/nodes/${n}`;
export const rk = { history: (c: string, l: string, n: string) => ["history", c, l, n] as const };

export function useTestMe(c: string, l: string, n: string) {
  const qc = useQueryClient();
  return {
    start: useMutation({ mutationFn: () => api<{ questions: TestQuestion[] }>(`${base(c, l, n)}/test-me`, { method: "POST" }) }),
    grade: useMutation({
      mutationFn: (items: { question: string; answer: string; source: SlideRef | null }[]) =>
        api<ResultRecord>(`${base(c, l, n)}/test-me/grade`, { method: "POST", json: { items } }),
      onSuccess: () => void qc.invalidateQueries({ queryKey: rk.history(c, l, n) }),
    }),
  };
}

export function useHistory(c: string, l: string, n: string) {
  return useQuery({ queryKey: rk.history(c, l, n), queryFn: () => api<ResultRecord[]>(`${base(c, l, n)}/history`) });
}

export function useNodePractice(c: string, l: string, n: string) {
  return useQuery({
    queryKey: ["practice", c, l, n],
    queryFn: () => api<PracticeItem[]>(`/courses/${c}/lectures/${l}/practice?node_id=${n}`),
  });
}
