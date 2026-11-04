import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { Note } from "./types";

export interface NoteDestination {
  course_id: string | null;
  lecture_id: string | null;
  node_id: string | null;
  label: string;
}

export interface InboxItem {
  id: string;
  text: string;
  created_at: string;
  suggestion: NoteDestination | null;
}

export interface Captured {
  where: "node" | "lecture" | "course" | "inbox";
  note: Note | null;
  inbox_item: InboxItem | null;
}

export const nk = {
  lecture: (c: string, l: string, n?: string | null) => ["notes", c, l, n ?? "*"] as const,
  course: (c: string) => ["notes", c] as const,
  inbox: ["inbox"] as const,
  dests: ["inbox-dests"] as const,
};

export function useLectureNotes(c: string, l: string, nodeId?: string | null) {
  return useQuery({
    queryKey: nk.lecture(c, l, nodeId),
    queryFn: () => api<Note[]>(`/courses/${c}/lectures/${l}/notes${nodeId ? `?node_id=${nodeId}` : ""}`),
  });
}

export function useNoteMutations(c: string, l: string | null) {
  const qc = useQueryClient();
  const base = l ? `/courses/${c}/lectures/${l}/notes` : `/courses/${c}/notes`;
  const done = () => void qc.invalidateQueries({ queryKey: ["notes"] });
  return {
    add: useMutation({
      mutationFn: (b: { text: string; node_id?: string | null }) => api<Note>(base, { method: "POST", json: b }),
      onSuccess: done,
    }),
    edit: useMutation({
      mutationFn: ({ id, text }: { id: string; text: string }) => api<Note>(`${base}/${id}`, { method: "PATCH", json: { text } }),
      onSuccess: done,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api<void>(`${base}/${id}`, { method: "DELETE" }),
      onSuccess: done,
    }),
  };
}

export function useCapture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { text: string; course_id?: string | null; lecture_id?: string | null; node_id?: string | null }) =>
      api<Captured>("/notes/capture", { method: "POST", json: b }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notes"] });
      void qc.invalidateQueries({ queryKey: nk.inbox });
    },
  });
}

export function useInbox() {
  return useQuery({ queryKey: nk.inbox, queryFn: () => api<InboxItem[]>("/inbox") });
}

export function useDestinations(enabled: boolean) {
  return useQuery({ queryKey: nk.dests, queryFn: () => api<NoteDestination[]>("/inbox/destinations"), enabled });
}

export function useInboxMutations() {
  const qc = useQueryClient();
  const done = () => {
    void qc.invalidateQueries({ queryKey: nk.inbox });
    void qc.invalidateQueries({ queryKey: ["notes"] });
  };
  return {
    suggest: useMutation({
      mutationFn: (id: string) => api<InboxItem>(`/inbox/${id}/suggest`, { method: "POST" }),
      onSuccess: (item) => qc.setQueryData<InboxItem[]>(nk.inbox, (old) => old?.map((i) => (i.id === item.id ? item : i))),
    }),
    file: useMutation({
      mutationFn: ({ id, dest }: { id: string; dest: NoteDestination }) => api<Captured>(`/inbox/${id}/file`, { method: "POST", json: dest }),
      onSuccess: done,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api<void>(`/inbox/${id}`, { method: "DELETE" }),
      onSuccess: done,
    }),
  };
}
