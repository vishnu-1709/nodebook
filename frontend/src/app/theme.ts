import type { Theme } from "../api/types";

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  try {
    localStorage.setItem("nodebook.theme", theme);
  } catch {
    /* ignore */
  }
}

export function initialTheme(): Theme {
  try {
    const t = localStorage.getItem("nodebook.theme");
    if (t === "light" || t === "dark" || t === "system") return t;
  } catch {
    /* ignore */
  }
  return "system";
}
