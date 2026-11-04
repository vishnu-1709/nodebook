import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { lk } from "./lectures";
import type { Exchange, MapDoc, Note, NodeThread, PracticeItem } from "./types";

export const tk = {
  thread: (c: string, l: string, n: string) => ["thread", c, l, n] as const,
  counts: (c: string, l: string) => ["kept-counts", c, l] as const,
};

const base = (c: string, l: string) => `/courses/${c}/lectures/${l}`;

export function useThread(c: string, l: string, n: string | null) {
  return useQuery({
    queryKey: tk.thread(c, l, n ?? ""),
    queryFn: () => api<NodeThread>(`${base(c, l)}/nodes/${n}/thread`),
    enabled: Boolean(n),
  });
}

export function useKeptCounts(c: string, l: string, enabled: boolean) {
  return useQuery({
    queryKey: tk.counts(c, l),
    queryFn: () => api<Record<string, number>>(`${base(c, l)}/threads/counts`),
    enabled,
  });
}

export function useThreadMutations(c: string, l: string, nodeId: string) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: tk.thread(c, l, nodeId) });
    void qc.invalidateQueries({ queryKey: tk.counts(c, l) });
  };
  const keep = useMutation({
    mutationFn: (id: string) => api<Exchange>(`${base(c, l)}/exchanges/${id}/keep`, { method: "POST" }),
    onSuccess: refresh,
  });
  const unkeep = useMutation({
    mutationFn: (id: string) => api<Exchange>(`${base(c, l)}/exchanges/${id}/unkeep`, { method: "POST" }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api<void>(`${base(c, l)}/exchanges/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  const toCard = useMutation({
    mutationFn: (id: string) => api<PracticeItem>(`${base(c, l)}/exchanges/${id}/to-card`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["practice", c, l] }),
  });
  const toNote = useMutation({
    mutationFn: (id: string) => api<Note>(`${base(c, l)}/exchanges/${id}/to-note`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["notes"] }),
  });
  const toNode = useMutation({
    mutationFn: (id: string) => api<MapDoc>(`${base(c, l)}/exchanges/${id}/to-node`, { method: "POST" }),
    onSuccess: (d) => qc.setQueryData(lk.map(c, l), d),
  });
  return { keep, unkeep, remove, toCard, toNote, toNode, refresh };
}
