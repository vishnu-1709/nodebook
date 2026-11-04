import { useCourses } from "../api/hooks";
import { useUi } from "../app/store";
import { PageHead } from "../components/PageHead";

function todayLabel(): string {
  return new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
}

export function Today() {
  const courses = useCourses();
  const open = useUi((s) => s.open);
  const empty = courses.isSuccess && courses.data.length === 0;
  return (
    <div className="content content-narrow">
      <PageHead
        kicker={todayLabel()}
        title="Today"
        actions={
          <>
            <button className="btn" onClick={() => open("quick_note")}>+ Quick note <span className="kbd">N</span></button>
            <button className="btn btn-primary" onClick={() => open("generate")}>Generate <span className="kbd">G</span></button>
          </>
        }
      />
      {empty ? (
        <div className="card stack empty-state">
          <h2>Start with a course</h2>
          <p className="muted">Create a course, then drop in lecture slides to get a mind map you can study from.</p>
          <div>
            <button className="btn btn-primary" onClick={() => open("new_course")}>Add your first course</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
