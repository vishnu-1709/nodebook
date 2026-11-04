import { NavLink } from "react-router-dom";
import { useCourses } from "../api/hooks";
import { useInbox } from "../api/notes";
import { useUi } from "../app/store";

export function Sidebar() {
  const courses = useCourses();
  const open = useUi((s) => s.open);
  const inbox = useInbox();
  const inboxCount = inbox.data?.length ?? 0;
  return (
    <nav className="sidebar" aria-label="Main">
      <div className="wordmark">Nodebook</div>
      <NavLink to="/" end className="nav-link">Today</NavLink>
      <NavLink to="/review" className="nav-link">
        Review
      </NavLink>
      <NavLink to="/inbox" className="nav-link">
        <span className="grow">Notes inbox</span>
        {inboxCount > 0 && <span className="badge" aria-label={`${inboxCount} unsorted`}>{inboxCount}</span>}
      </NavLink>
      <div className="nav-section">Courses</div>
      {courses.data?.map((c) => (
        <NavLink key={c.id} to={`/course/${c.id}`} className="nav-link">
          {c.name}
        </NavLink>
      ))}
      <button className="btn btn-ghost btn-left" onClick={() => open("new_course")}>
        + New course
      </button>
      <div className="sidebar-foot">
        <NavLink to="/settings" className="nav-link">Settings</NavLink>
        <button className="btn btn-ghost btn-sm btn-left" onClick={() => open("help")}>
          Shortcuts <span className="kbd">?</span>
        </button>
      </div>
    </nav>
  );
}
