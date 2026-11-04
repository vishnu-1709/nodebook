import { useEffect, useRef } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { isCollapsed, screenType, useSidebar } from "./sidebar";
import { useSettings } from "../api/hooks";
import { anyModalOpen } from "../components/Modal";
import { NewCourseDialog } from "../components/NewCourseDialog";
import { QuickNote } from "../components/QuickNote";
import { GeneratePanel } from "../components/GeneratePanel";
import { PomodoroRunner } from "../components/PomodoroRunner";
import { ReminderPopover } from "../components/ReminderPopover";
import { toggle, usePomodoro } from "./pomodoro";
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
  const location = useLocation();
  const stype = screenType(location.pathname);
  const prefs = useSidebar((s) => s.prefs);
  const toggleSidebar = useSidebar((s) => s.toggle);
  const collapsed = isCollapsed(prefs, stype);
  const stypeRef = useRef(stype);
  stypeRef.current = stype;

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
        case "toggle_sidebar":
          useSidebar.getState().toggle(stypeRef.current);
          break;
        case "pomodoro": {
          const p = usePomodoro.getState();
          p.set(toggle(p.s, Date.now()));
          break;
        }
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

  if (settings.data && !settings.data.onboarded) return <Navigate to="/welcome" replace />;

  return (
    <div className={collapsed ? "shell rail-mode" : "shell"}>
      <Sidebar collapsed={collapsed} onToggle={() => toggleSidebar(stype)} />
      <main className="main">
        <Outlet />
      </main>
      {overlay === "help" && <ShortcutHelp onClose={close} />}
      {overlay === "new_course" && <NewCourseDialog onClose={close} />}
      {overlay === "quick_note" && <QuickNote onClose={close} />}
      {overlay === "generate" && <GeneratePanel onClose={close} />}
      {overlay === "reminder" && <ReminderPopover onClose={close} />}
      <PomodoroRunner />
      {toast && <div className="app-toast" role="status">{toast}</div>}
    </div>
  );
}
