import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateCourse } from "../api/hooks";
import { errorMessage } from "../api/client";
import { Modal } from "./Modal";

export function NewCourseDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const create = useCreateCourse();
  const nav = useNavigate();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    create.mutate(name.trim(), {
      onSuccess: (c) => {
        onClose();
        nav(`/course/${c.id}`);
      },
    });
  };
  return (
    <Modal title="New course" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <label className="field">
          <span>Course name</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Signals and Systems" maxLength={120} />
        </label>
        {create.isError && <p className="banner banner-error">{errorMessage(create.error)}</p>}
        <div className="row">
          <span className="spacer" />
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={!name.trim() || create.isPending}>Create course</button>
        </div>
      </form>
    </Modal>
  );
}
