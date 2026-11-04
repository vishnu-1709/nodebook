import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/client";
import { postSSE } from "../api/sse";
import { useThread, useThreadMutations } from "../api/threads";
import type { Exchange, Message, MessageKind } from "../api/types";

interface Props {
  courseId: string;
  lectureId: string;
  nodeId: string;
  nodeLabel: string;
  /** Draft text lives in the parent so it survives Focus ↔ quick switches. */
  draft: string;
  setDraft: (s: string) => void;
}

type Mode = "normal" | "try_first" | "hint";
type Action = "ask" | "attempt" | "why" | "example";

interface Live {
  exchangeId: string | null;
  user: Message | null;
  kind: MessageKind;
  text: string;
  error: string;
}

const KIND_LABEL: Partial<Record<MessageKind, string>> = {
  try_first: "Your turn first",
  hint: "Hint",
  attempt: "Your attempt",
};

function userTurns(ex: Exchange): number {
  return ex.messages.filter((m) => m.role === "user").length;
}

export function ThreadTab({ courseId, lectureId, nodeId, nodeLabel, draft, setDraft }: Props) {
  const thread = useThread(courseId, lectureId, nodeId);
  const muts = useThreadMutations(courseId, lectureId, nodeId);
  const [tryFirst, setTryFirst] = useState(true);
  const [hintOnly, setHintOnly] = useState(false);
  const [active, setActive] = useState<string | null>(null); // exchange being continued
  const [live, setLive] = useState<Live | null>(null);
  const [undo, setUndo] = useState<{ id: string; timer: number } | null>(null);
  const [flash, setFlash] = useState("");
  const abort = useRef<AbortController | null>(null);
  const lastReq = useRef<{ action: Action; exchangeId: string | null; content: string } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setActive(null);
    setLive(null);
    return () => abort.current?.abort();
  }, [nodeId]);
  useEffect(() => () => { if (undo) window.clearTimeout(undo.timer); }, [undo]);

  const all = [...(thread.data?.kept ?? []), ...(thread.data?.recent ?? [])];
  const activeEx = all.find((e) => e.id === active) ?? null;
  const awaitingAttempt = activeEx?.messages.at(-1)?.kind === "try_first" || live?.kind === "try_first";
  const mode: Mode = hintOnly ? "hint" : tryFirst ? "try_first" : "normal";
  const streaming = live !== null && !live.error;

  const send = async (action: Action, exchangeId: string | null, content = draft) => {
    if (streaming) return;
    if ((action === "ask" || action === "attempt") && !content.trim()) return;
    const ctrl = new AbortController();
    abort.current = ctrl;
    lastReq.current = { action, exchangeId, content };
    setLive({ exchangeId, user: null, kind: "answer", text: "", error: "" });
    if (action === "ask" || action === "attempt") setDraft("");
    try {
      await postSSE(
        `/courses/${courseId}/lectures/${lectureId}/nodes/${nodeId}/ask`,
        { content, mode, action, exchange_id: exchangeId },
        (e) => {
          if (e.type === "start") {
            setActive(e.exchange_id as string);
            setLive((l) => l && { ...l, exchangeId: e.exchange_id as string, user: e.user as Message, kind: e.kind as MessageKind });
          } else if (e.type === "delta") {
            setLive((l) => l && { ...l, text: l.text + (e.text as string) });
            bottom.current?.scrollIntoView({ block: "nearest" });
          } else if (e.type === "error") {
            setLive((l) => l && { ...l, error: e.message as string });
          } else if (e.type === "done") {
            muts.refresh();
            setLive(null);
          }
        },
        ctrl.signal,
      );
    } catch (err) {
      if (!ctrl.signal.aborted) setLive((l) => ({ ...(l ?? { exchangeId, user: null, kind: "answer", text: "" }), error: errorMessage(err) }));
    }
  };

  const doUnkeep = (id: string) => {
    muts.unkeep.mutate(id);
    if (undo) window.clearTimeout(undo.timer);
    const timer = window.setTimeout(() => setUndo(null), 5000);
    setUndo({ id, timer });
  };

  const note = (text: string) => {
    setFlash(text);
    window.setTimeout(() => setFlash(""), 2500);
  };

  const renderExchange = (ex: Exchange, kept: boolean) => {
    const isLive = live && live.exchangeId === ex.id;
    const last = ex.messages.at(-1);
    return (
      <article key={ex.id} className={kept ? "exchange kept" : "exchange recent"} aria-label={kept ? "Kept question" : "Recent doubt"}>
        {ex.messages.map((m, i) => <Bubble key={i} m={m} />)}
        {isLive && live.user && <Bubble m={live.user} />}
        {isLive && <Bubble m={{ role: "assistant", kind: live.kind, content: live.text || "…" }} />}
        {isLive && live.error && <ErrorRow error={live.error} onRetry={retry} onDismiss={() => setLive(null)} />}
        {!isLive && (
          <div className="exchange-actions row wrap">
            {kept ? (
              <>
                <button className="btn btn-ghost btn-sm" onClick={() => doUnkeep(ex.id)}>Un-keep</button>
                <button className="btn btn-ghost btn-sm" onClick={() => muts.toCard.mutate(ex.id, { onSuccess: () => note("Flashcard added to Practice.") })}>Make flashcard</button>
                <button className="btn btn-ghost btn-sm" onClick={() => muts.toNote.mutate(ex.id, { onSuccess: () => note("Pinned as a note.") })}>Pin as note</button>
                <button className="btn btn-ghost btn-sm" onClick={() => muts.toNode.mutate(ex.id, { onSuccess: () => note("Added as a child node.") })}>Add as child node</button>
              </>
            ) : (
              <button className="btn btn-sm" onClick={() => muts.keep.mutate(ex.id)}>Keep</button>
            )}
            {last?.role === "assistant" && last.kind === "answer" && (
              <details className="more-help">
                <summary className="btn btn-ghost btn-sm">More help ▾</summary>
                <div className="row">
                  <button className="btn btn-sm" onClick={() => void send("why", ex.id, "")}>Explain why</button>
                  <button className="btn btn-sm" onClick={() => void send("example", ex.id, "")}>Give example</button>
                </div>
              </details>
            )}
            {active !== ex.id && last?.kind !== "try_first" && (
              <button className="btn btn-ghost btn-sm" onClick={() => setActive(ex.id)}>Follow up</button>
            )}
            {active === ex.id && <span className="small muted">Your next message continues this</span>}
          </div>
        )}
        {!kept && !isLive && userTurns(ex) >= 3 && (
          <p className="keep-nudge small">You've gone back and forth on this a few times. Keep this? It'll stay on “{nodeLabel}”.</p>
        )}
      </article>
    );
  };

  const retry = () => {
    const r = lastReq.current;
    const exId = live?.exchangeId ?? r?.exchangeId ?? null;
    setLive(null);
    if (r) window.setTimeout(() => void send(r.action, exId, r.content), 0);
  };

  const kept = thread.data?.kept ?? [];
  const recent = thread.data?.recent ?? [];
  const newLive = live && !all.some((e) => e.id === live.exchangeId);

  return (
    <div className="thread">
      <div className="thread-scroll">
        {thread.isLoading && <p className="muted small">Loading…</p>}
        {kept.length === 0 && recent.length === 0 && !live && (
          <p className="muted small">Ask anything about this topic. Answers come only from your slides.</p>
        )}
        {kept.map((ex) => renderExchange(ex, true))}
        {recent.length > 0 && <h3 className="small muted recent-head">Recent doubts · gone after 7 days unless kept</h3>}
        {recent.map((ex) => renderExchange(ex, false))}
        {newLive && (
          <article className="exchange recent">
            {live.user && <Bubble m={live.user} />}
            <Bubble m={{ role: "assistant", kind: live.kind, content: live.text || "…" }} />
            {live.error && <ErrorRow error={live.error} onRetry={retry} onDismiss={() => setLive(null)} />}
          </article>
        )}
        <div ref={bottom} />
      </div>

      {undo && (
        <div className="toast row" role="status">
          <span>Removed from kept.</span>
          <button className="btn btn-sm" onClick={() => { muts.keep.mutate(undo.id); window.clearTimeout(undo.timer); setUndo(null); }}>Undo</button>
        </div>
      )}
      {flash && <div className="toast" role="status">{flash}</div>}

      <form
        className="ask-box"
        onSubmit={(e) => {
          e.preventDefault();
          if (awaitingAttempt && active) void send("attempt", active);
          else void send("ask", active);
        }}
      >
        <label className="visually-hidden" htmlFor="ask-input">{awaitingAttempt ? "Your attempt" : "Ask about this topic"}</label>
        <textarea
          id="ask-input"
          className="textarea"
          value={draft}
          rows={3}
          placeholder={awaitingAttempt ? "What do you think? Give it a try…" : `Ask about “${nodeLabel}”…`}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <div className="row wrap">
          <label className="row small">
            <input type="checkbox" checked={tryFirst} disabled={hintOnly} onChange={(e) => setTryFirst(e.target.checked)} /> Try first
          </label>
          <label className="row small">
            <input type="checkbox" checked={hintOnly} onChange={(e) => setHintOnly(e.target.checked)} /> Hint only
          </label>
          {active && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setActive(null)}>New question</button>
          )}
          <span className="spacer" />
          <button type="submit" className="btn btn-primary btn-sm" disabled={streaming || !draft.trim()}>
            {awaitingAttempt ? "Send attempt" : "Ask"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Bubble({ m }: { m: Message }) {
  const label = KIND_LABEL[m.kind];
  return (
    <div className={`bubble bubble-${m.role} kind-${m.kind}`}>
      {label && <span className="bubble-kind small muted">{label}</span>}
      <p className="bubble-text">{m.content}</p>
    </div>
  );
}

function ErrorRow({ error, onRetry, onDismiss }: { error: string; onRetry: () => void; onDismiss: () => void }) {
  return (
    <div className="banner banner-error small">
      <span>{error}</span>
      <span className="spacer" />
      <button className="btn btn-sm" onClick={onRetry}>Retry</button>
      <button className="btn btn-ghost btn-sm" onClick={onDismiss}>Dismiss</button>
    </div>
  );
}
