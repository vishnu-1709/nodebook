import { useState } from "react";
import { NavLink } from "react-router-dom";
import { useCourses, useOllamaStatus, useSettings } from "../api/hooks";
import { useInbox } from "../api/notes";
import { useUi } from "../app/store";

export function Sidebar() {
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

  return (
    <nav className={menu ? "sidebar open" : "sidebar"} aria-label="Main">
      <div className="wordmark">Nodebook</div>
      <button className="btn btn-ghost btn-sm menu-btn" aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? "Close" : "Menu"}</button>
      <NavLink to="/" end className="nav-link" onClick={close}>Today</NavLink>
      <NavLink to="/review" className="nav-link" onClick={close}><span className="grow">Review</span></NavLink>
      <NavLink to="/inbox" className="nav-link" onClick={close}>
        <span className="grow">Notes inbox</span>
        {inboxCount > 0 && <span className="nav-count" aria-label={`${inboxCount} unsorted`}>{inboxCount}</span>}
      </NavLink>
      <div className="nav-section label-caps">Courses</div>
      {courses.data?.map((c) => (
        <NavLink key={c.id} to={`/course/${c.id}`} className="nav-link" onClick={close}>{c.name}</NavLink>
      ))}
      <button className="btn btn-dashed btn-sm new-course" onClick={() => { close(); open("new_course"); }}>+ New course</button>
      <div className="sidebar-foot">
        <NavLink to="/settings" className="nav-link" onClick={close}>Settings</NavLink>
        <button className="nav-link btn-ghost link-reset" onClick={() => { close(); open("help"); }}>
          <span className="grow">Shortcuts</span><span className="hint">?</span>
        </button>
        {ollama.data && (
          <NavLink to="/settings" className="ollama-line" onClick={close}>
            <span className={up ? "ollama-dot" : "ollama-dot down"} aria-hidden="true" />
            {up ? <span className="truncate">Ollama running{model ? ` · ${model}` : ""}</span> : <span>Ollama not running</span>}
          </NavLink>
        )}
      </div>
    </nav>
  );
}
