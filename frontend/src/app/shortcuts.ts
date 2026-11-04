// Global keyboard shortcuts (SPEC §5.1). Pure logic lives here so it can be tested.

export type ShortcutAction =
  | "quick_note"
  | "generate"
  | "pomodoro"
  | "reminder"
  | "expand_panel"
  | "escape"
  | "help"
  | "toggle_sidebar";

export const SHORTCUTS: { key: string; action: ShortcutAction; label: string }[] = [
  { key: "N", action: "quick_note", label: "Quick note" },
  { key: "G", action: "generate", label: "Generate" },
  { key: "P", action: "pomodoro", label: "Start / pause pomodoro" },
  { key: "R", action: "reminder", label: "Add reminder" },
  { key: "F", action: "expand_panel", label: "Expand side panel (Focus mode)" },
  { key: "Esc", action: "escape", label: "Close / collapse" },
  { key: "?", action: "help", label: "Show shortcuts" },
  { key: "Ctrl/Cmd+B", action: "toggle_sidebar", label: "Collapse / expand the sidebar" },
];

/** Map keys (UI.md §3.2) — handled by the map itself; listed in the ? help. */
export const MAP_KEYS: { key: string; label: string }[] = [
  { key: "Double-click / F2", label: "Rename node" },
  { key: "Tab", label: "Add child" },
  { key: "Enter", label: "Add sibling" },
  { key: "Delete / Backspace", label: "Delete node (undo toast)" },
  { key: "Drag", label: "Move node" },
  { key: "Click arrow", label: "Collapse / expand branch" },
  { key: "F", label: "Open selected node in Focus mode" },
  { key: "Ctrl/Cmd+Z", label: "Undo map edit" },
  { key: "Ctrl/Cmd+Shift+Z", label: "Redo map edit" },
  { key: "Right-click", label: "Rename, add, AI actions, delete" },
];

const KEYMAP: Record<string, ShortcutAction> = {
  n: "quick_note",
  g: "generate",
  p: "pomodoro",
  r: "reminder",
  f: "expand_panel",
  "?": "help",
  Escape: "escape",
};

export interface KeyLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  target?: EventTarget | null;
}

export function isTypingTarget(target: EventTarget | null | undefined): boolean {
  if (!target || typeof (target as HTMLElement).tagName !== "string") return false;
  const el = target as HTMLElement;
  const tag = el.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (el.isContentEditable) return true;
  const ce = el.getAttribute?.("contenteditable");
  return ce === "" || ce === "true" || ce === "plaintext-only";
}

/** Returns the action for a key event, or null. Esc works even while typing (it blurs/closes). */
export function actionFor(e: KeyLike): ShortcutAction | null {
  if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "b" && !isTypingTarget(e.target)) return "toggle_sidebar";
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  if (e.key === "Escape") return "escape";
  if (isTypingTarget(e.target)) return null;
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  return KEYMAP[k] ?? (e.key === "?" ? "help" : null);
}
