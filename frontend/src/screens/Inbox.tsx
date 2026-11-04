import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/client";
import { useDestinations, useInbox, useInboxMutations, type InboxItem, type NoteDestination } from "../api/notes";
import { useUi } from "../app/store";
import { PageHead } from "../components/PageHead";

export function InboxScreen() {
  const inbox = useInbox();
  const m = useInboxMutations();
  const asked = useRef(new Set<string>());

  // ask the model for a destination, one item at a time
  useEffect(() => {
    const next = inbox.data?.find((i) => !i.suggestion && !asked.current.has(i.id));
    if (!next || m.suggest.isPending) return;
    asked.current.add(next.id);
    m.suggest.mutate(next.id);
  }, [inbox.data, m.suggest]);

  return (
    <div className="content content-narrow">
      <PageHead title="Notes inbox" />
      {inbox.data?.length === 0 && <p className="muted">Nothing to sort. Quick notes taken outside a course land here.</p>}
      <ul className="note-list">
        {inbox.data?.map((it) => <InboxRow key={it.id} item={it} suggesting={m.suggest.isPending && m.suggest.variables === it.id} />)}
      </ul>
      {m.suggest.isError && <p className="banner banner-error small">Couldn't get a suggestion: {errorMessage(m.suggest.error)}</p>}
    </div>
  );
}

function InboxRow({ item, suggesting }: { item: InboxItem; suggesting: boolean }) {
  const m = useInboxMutations();
  const [changing, setChanging] = useState(false);
  const dests = useDestinations(changing);
  const showToast = useUi((s) => s.showToast);
  const s = item.suggestion && item.suggestion.course_id ? item.suggestion : null;

  const file = (dest: NoteDestination) =>
    m.file.mutate({ id: item.id, dest }, { onSuccess: () => showToast(`Filed to ${dest.label}`) });

  return (
    <li className="note">
      <p className="note-text">{item.text}</p>
      <div className="row wrap">
        {suggesting && <span className="small muted">Finding a place…</span>}
        {s && !changing && (
          <button className="btn btn-sm btn-primary" onClick={() => file(s)}>File to {s.label}</button>
        )}
        {!s && !suggesting && item.suggestion && <span className="small muted">No good match — pick one.</span>}
        {changing ? (
          <select
            className="select select-sm"
            aria-label="Destination"
            defaultValue=""
            onChange={(e) => {
              const d = dests.data?.[Number(e.target.value)];
              if (d) file(d);
            }}
          >
            <option value="" disabled>{dests.isLoading ? "Loading…" : "Choose where…"}</option>
            {dests.data?.map((d, i) => <option key={i} value={i}>{d.label}</option>)}
          </select>
        ) : (
          <button className="btn btn-sm" onClick={() => setChanging(true)}>Change</button>
        )}
        <span className="spacer" />
        <button className="btn btn-ghost btn-sm" onClick={() => window.confirm("Delete this note?") && m.remove.mutate(item.id)}>Delete</button>
      </div>
    </li>
  );
}
