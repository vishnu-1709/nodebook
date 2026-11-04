import { create } from "zustand";

export type Overlay = "none" | "quick_note" | "generate" | "reminder" | "help" | "new_course";

/** Where the user currently is — used to file quick notes and pre-fill Generate. */
export interface StudyContext {
  courseId: string | null;
  lectureId: string | null;
  nodeId: string | null;
}

interface UiState {
  toast: string;
  showToast: (msg: string) => void;
  overlay: Overlay;
  open: (o: Overlay) => void;
  close: () => void;
  context: StudyContext;
  setContext: (c: Partial<StudyContext>) => void;
}

let toastTimer: number | undefined;

export const useUi = create<UiState>((set) => ({
  toast: "",
  showToast: (toast) => {
    window.clearTimeout(toastTimer);
    set({ toast });
    toastTimer = window.setTimeout(() => set({ toast: "" }), 1500);
  },
  overlay: "none",
  open: (overlay) => set({ overlay }),
  close: () => set({ overlay: "none" }),
  context: { courseId: null, lectureId: null, nodeId: null },
  setContext: (c) => set((s) => ({ context: { ...s.context, ...c } })),
}));

/** Lightweight event bus for shortcut actions that screens handle themselves (e.g. F, Esc). */
type Listener = (action: string) => boolean | void;
const listeners = new Set<Listener>();
export function onShortcut(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
/** Returns true if a screen handled it. Last-registered listener wins. */
export function emitShortcut(action: string): boolean {
  const arr = Array.from(listeners).reverse();
  for (const fn of arr) if (fn(action) === true) return true;
  return false;
}
