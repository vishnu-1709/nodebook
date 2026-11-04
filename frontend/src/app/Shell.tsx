import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { useSettings } from "../api/hooks";
import { anyModalOpen } from "../components/Modal";
import { NewCourseDialog } from "../components/NewCourseDialog";
import { QuickNote } from "../components/QuickNote";
import { ShortcutHelp } from "../components/ShortcutHelp";
import { Sidebar } from "../components/Sidebar";
import { actionFor } from "./shortcuts";
import { emitShortcut, useUi } from "./store";
import { applyTheme } from "./theme";

export function Shell() {
  const overlay = useUi((s) => s.overlay);
  const open = useUi((s) => s.open);
  const close = useUi((s) => s.close);
  const settings = useSettings();
  const toast = useUi((s) => s.toast);

  useEffect(() => {
    if (settings.data) applyTheme(settings.data.theme);
  }, [settings.data]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const action = actionFor(e);
      if (!action || anyModalOpen()) return;
      const current = useUi.getState().overlay;
      if (action === "escape") {
        if (current !== "none") {
          e.preventDefault();
          close();
          return;
        }
        if (emitShortcut("escape")) e.preventDefault();
        else (document.activeElement as HTMLElement | null)?.blur?.();
        return;
      }
      if (current !== "none" && action !== "help") return;
      e.preventDefault();
      switch (action) {
        case "quick_note":
        case "generate":
        case "reminder":
          if (!emitShortcut(action)) open(action);
          break;
        case "help":
          open(current === "help" ? "none" : "help");
          break;
        default:
          emitShortcut(action);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  return (
    <div className="shell">
      <Sidebar />
      <main className="main">
        <Outlet />
      </main>
      {overlay === "help" && <ShortcutHelp onClose={close} />}
      {overlay === "new_course" && <NewCourseDialog onClose={close} />}
      {overlay === "quick_note" && <QuickNote onClose={close} />}
      {toast && <div className="app-toast" role="status">{toast}</div>}
    </div>
  );
}
