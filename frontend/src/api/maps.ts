import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { lk } from "./lectures";
import type { MapDoc, SlideRef, Status } from "./types";
import type { TreeIn } from "../components/mapData";

export type NodeAction = "expand" | "split" | "merge" | "simplify";

export interface ProposalPart {
  label: string;
  sources: SlideRef[];
}

export interface Proposal {
  action: NodeAction;
  node_id: string;
  sibling_id: string | null;
  label: string | null;
  parts: ProposalPart[];
}

function base(c: string, l: string): string {
  return `/courses/${c}/lectures/${l}/map`;
}

export function useMapMutations(courseId: string, lectureId: string) {
  const qc = useQueryClient();
  const put = (doc: MapDoc) => qc.setQueryData(lk.map(courseId, lectureId), doc);
  const refreshLecture = () => void qc.invalidateQueries({ queryKey: lk.lecture(courseId, lectureId) });

  const structure = useMutation({
    mutationFn: (tree: TreeIn) => api<MapDoc>(`${base(courseId, lectureId)}/structure`, { method: "PUT", json: tree }),
    onSuccess: (d) => {
      put(d);
      refreshLecture();
    },
    onError: () => void qc.invalidateQueries({ queryKey: lk.map(courseId, lectureId) }),
  });
  const patchNode = useMutation({
    mutationFn: ({ id, ...body }: { id: string; label?: string; status?: Status; studied?: boolean; status_mode?: "auto" }) =>
      api<MapDoc>(`${base(courseId, lectureId)}/nodes/${id}`, { method: "PATCH", json: body }),
    onSuccess: put,
  });
  const suggest = useMutation({
    mutationFn: ({ id, action, sibling_id }: { id: string; action: NodeAction; sibling_id?: string }) =>
      api<Proposal>(`${base(courseId, lectureId)}/nodes/${id}/suggest`, { method: "POST", json: { action, sibling_id } }),
  });
  const apply = useMutation({
    mutationFn: (p: Proposal) => api<MapDoc>(`${base(courseId, lectureId)}/apply`, { method: "POST", json: p }),
    onSuccess: (d) => {
      put(d);
      refreshLecture();
    },
  });
  const addUncovered = useMutation({
    mutationFn: () => api<MapDoc>(`${base(courseId, lectureId)}/add-uncovered`, { method: "POST" }),
    onSuccess: (d) => {
      put(d);
      refreshLecture();
    },
  });
  return { structure, patchNode, suggest, apply, addUncovered };
}
