import { create } from "zustand";

// Collapsible sidebar (UI.md §2): remembered per screen type; the lecture map opens collapsed.

export type ScreenType = "today" | "review" | "inbox" | "course" | "lecture" | "settings" | "other";

export function screenType(pathname: string): ScreenType {
  if (pathname === "/" || pathname === "") return "today";
  if (/^\/course\/[^/]+\/lecture\//.test(pathname)) return "lecture";
  if (pathname.startsWith("/course/")) return "course";
  if (pathname.startsWith("/review")) return "review";
  if (pathname.startsWith("/inbox")) return "inbox";
  if (pathname.startsWith("/settings")) return "settings";
  return "other";
}

const DEFAULTS: Partial<Record<ScreenType, boolean>> = { lecture: true };
const KEY = "nodebook.sidebar";

function load(): Partial<Record<ScreenType, boolean>> {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as Partial<Record<ScreenType, boolean>>;
  } catch {
    /* ignore */
  }
  return {};
}

export function isCollapsed(prefs: Partial<Record<ScreenType, boolean>>, t: ScreenType): boolean {
  return prefs[t] ?? DEFAULTS[t] ?? false;
}

interface SidebarStore {
  prefs: Partial<Record<ScreenType, boolean>>;
  toggle: (t: ScreenType) => void;
  set: (t: ScreenType, collapsed: boolean) => void;
}

export const useSidebar = create<SidebarStore>((set, get) => ({
  prefs: load(),
  toggle: (t) => get().set(t, !isCollapsed(get().prefs, t)),
  set: (t, collapsed) => {
    const prefs = { ...get().prefs, [t]: collapsed };
    try {
      localStorage.setItem(KEY, JSON.stringify(prefs));
    } catch {
      /* ignore */
    }
    set({ prefs });
  },
}));

export function initials(name: string): string {
  const words = name.split(/\s+/).filter((w) => /[A-Za-z0-9]/.test(w));
  const ini = words.filter((w) => !/^(and|of|the|to|for|in|&)$/i.test(w)).map((w) => w[0]!.toUpperCase());
  return (ini.length ? ini : [name[0]?.toUpperCase() ?? "?"]).slice(0, 2).join("");
}
