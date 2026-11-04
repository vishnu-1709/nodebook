import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { JobInfo } from "./types";

export interface SystemInfo {
  version: string;
  ram_gb: number;
  platform: string;
  data_dir: string;
  onboarded: boolean;
}

export interface RecModel {
  name: string;
  size_gb: number;
  why: string;
  vision: boolean;
  installed: boolean;
}

export interface Recommended {
  ram_gb: number;
  tier_label: string;
  map: RecModel[];
  study: RecModel[];
}

export function useSystem() {
  return useQuery({ queryKey: ["system"], queryFn: () => api<SystemInfo>("/system") });
}

export function useRecommended() {
  return useQuery({ queryKey: ["recommended"], queryFn: () => api<Recommended>("/models/recommended") });
}

export function usePull() {
  return useMutation({ mutationFn: (name: string) => api<JobInfo>("/ollama/pull", { method: "POST", json: { name } }) });
}

export function useTestMap() {
  return useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api<JobInfo>("/ollama/test-map", { method: "POST", body: fd });
    },
  });
}

export function useRefreshModels() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["recommended"] });
    void qc.invalidateQueries({ queryKey: ["ollama"] });
  };
}
