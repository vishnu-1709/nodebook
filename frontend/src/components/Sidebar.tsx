import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useCourses, useOllamaStatus, useSettings } from "../api/hooks";
import { useInbox } from "../api/notes";
import { initials } from "../app/sidebar";
import { useUi } from "../app/store";

const I = {
  today: <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><rect x="2.5" y="3.5" width="13" height="12" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M2.5 7h13M6 2v3M12 2v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>,
  review: <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><rect x="3" y="5" width="10" height="10" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M6 2.5h7.5A1.5 1.5 0 0 1 15 4v8.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>,
  inbox: <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M2.5 10.5l2-6.5h9l2 6.5v4a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /><path d="M2.5 10.5h4l1 2h3l1-2h4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>,
  settings: <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M9 1.8v2M9 14.2v2M1.8 9h2M14.2 9h2M3.9 3.9l1.4 1.4M12.7 12.7l1.4 1.4M3.9 14.1l1.4-1.4M12.7 5.3l1.4-1.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>,
  collapse: <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="2.5" width="12" height="11" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M6 2.5v11" stroke="currentColor" strokeWidth="1.5" /></svg>,
};

interface Props {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: Props) {
  const courses = useCourses();
  const open = useUi((s) => s.open);
  const inbox = useInbox();
  const ollama = useOllamaStatus();
  const settings = useSettings();
  const [menu, setMenu] = useState(false);
  const inboxCount = inbox.data?.length ?? 0;
  const up = ollama.data?.status.reachable;
  const model = settings.data?.study_model ?? settings.data?.map_model;
  const close = () => setMenu(false);

  // Rail item: icon + tooltip label; expanded item: icon-less text row (UI.md §2)
  const item = (to: string, label: string, icon: ReactNode, badge?: ReactNode, end?: boolean) => (
    <NavLink to={to} end={end} className="nav-link" onClick={close} title={collapsed ? label : undefined} aria-label={collapsed ? label : undefined}>
      {collapsed ? <span className="rail-icon">{icon}</span> : <span className="grow">{label}</span>}
      {badge}
    </NavLink>
  );
  const inboxBadge = inboxCount > 0 ? <span className={collapsed ? "rail-badge" : "nav-count"} aria-label={`${inboxCount} unsorted`}>{inboxCount}</span> : null;

  return (
    <nav className={`sidebar${collapsed ? " rail" : ""}${menu ? " open" : ""}`} aria-label="Main">
      <div className="side-top">
        {collapsed ? (
          <button className="rail-mark" onClick={onToggle} title="Expand sidebar (Ctrl/Cmd+B)" aria-label="Expand sidebar">N</button>
        ) : (
          <>
            <div className="wordmark">Nodebook</div>
            <button className="side-toggle" onClick={onToggle} title="Collapse sidebar (Ctrl/Cmd+B)" aria-label="Collapse sidebar">{I.collapse}</button>
          </>
        )}
      </div>
      <button className="btn btn-ghost btn-sm menu-btn" aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? "Close" : "Menu"}</button>
      {item("/", "Today", I.today, undefined, true)}
      {item("/review", "Review", I.review)}
      {item("/inbox", "Notes inbox", I.inbox, inboxBadge)}
      {!collapsed && <div className="nav-section label-caps">Courses</div>}
      {collapsed && <div className="rail-sep" aria-hidden="true" />}
      {courses.data?.map((c) => (
        <NavLink key={c.id} to={`/course/${c.id}`} className="nav-link" onClick={close} title={collapsed ? c.name : undefined} aria-label={collapsed ? c.name : undefined}>
          {collapsed ? <span className="rail-initials">{initials(c.name)}</span> : c.name}
        </NavLink>
      ))}
      <button className={collapsed ? "rail-add" : "btn btn-dashed btn-sm new-course"} title={collapsed ? "New course" : undefined}
        aria-label={collapsed ? "New course" : undefined} onClick={() => { close(); open("new_course"); }}>
        {collapsed ? "+" : "+ New course"}
      </button>
      <div className="sidebar-foot">
        {item("/settings", "Settings", I.settings)}
        <button className="nav-link link-reset" onClick={() => { close(); open("help"); }} title={collapsed ? "Shortcuts (?)" : undefined} aria-label={collapsed ? "Shortcuts" : undefined}>
          {collapsed ? <span className="rail-icon hint">?</span> : <><span className="grow">Shortcuts</span><span className="hint">?</span></>}
        </button>
        {ollama.data && (
          <NavLink to="/settings" className="ollama-line" onClick={close}
            title={collapsed ? (up ? `Ollama running${model ? ` · ${model}` : ""}` : "Ollama not running") : undefined}>
            <span className={up ? "ollama-dot" : "ollama-dot down"} aria-hidden="true" />
            {!collapsed && (up ? <span className="truncate">Ollama running{model ? ` · ${model}` : ""}</span> : <span>Ollama not running</span>)}
            {collapsed && <span className="visually-hidden">{up ? "Ollama running" : "Ollama not running"}</span>}
          </NavLink>
        )}
      </div>
    </nav>
  );
}
