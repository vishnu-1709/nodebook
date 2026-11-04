// Global keyboard shortcuts (SPEC §5.1). Pure logic lives here so it can be tested.

export type ShortcutAction =
  | "quick_note"
  | "generate"
  | "pomodoro"
  | "reminder"
  | "expand_panel"
  | "escape"
  | "help";

export const SHORTCUTS: { key: string; action: ShortcutAction; label: string }[] = [
  { key: "N", action: "quick_note", label: "Quick note" },
  { key: "G", action: "generate", label: "Generate" },
  { key: "P", action: "pomodoro", label: "Start / pause pomodoro" },
  { key: "R", action: "reminder", label: "Add reminder" },
  { key: "F", action: "expand_panel", label: "Expand side panel (Focus mode)" },
  { key: "Esc", action: "escape", label: "Close / collapse" },
  { key: "?", action: "help", label: "Show shortcuts" },
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
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  if (e.key === "Escape") return "escape";
  if (isTypingTarget(e.target)) return null;
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  return KEYMAP[k] ?? (e.key === "?" ? "help" : null);
}
