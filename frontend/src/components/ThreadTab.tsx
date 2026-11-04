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

function userTurns(ex: Exchange): number {
  return ex.messages.filter((m) => m.role === "user").length;
}

function daysLeft(ex: Exchange): number {
  if (!ex.expires_at) return 7;
  return Math.max(0, Math.ceil((new Date(ex.expires_at).getTime() - Date.now()) / 86_400_000));
}

const PIN = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
    <path d="M10.5 1.5l4 4-2.2.8-2.6 2.6.3 3.1-1.5 1.5-2.6-2.6L2.5 14.3l-.8-.8 3.4-3.4L2.5 7.5 4 6l3.1.3 2.6-2.6z" fill="currentColor" />
  </svg>
);

export function ThreadTab({ courseId, lectureId, nodeId, nodeLabel, draft, setDraft }: Props) {
  const thread = useThread(courseId, lectureId, nodeId);
  const muts = useThreadMutations(courseId, lectureId, nodeId);
  const [tryFirst, setTryFirst] = useState(true);
  const [hintOnly, setHintOnly] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [active, setActive] = useState<string | null>(null);
  const [live, setLive] = useState<Live | null>(null);
  const [undo, setUndo] = useState<{ id: string; timer: number } | null>(null);
  const [declined, setDeclined] = useState<Set<string>>(new Set());
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

  const kept = thread.data?.kept ?? [];
  const recent = thread.data?.recent ?? [];
  const all = [...kept, ...recent];
  const activeEx = all.find((e) => e.id === active) ?? null;
  const awaitingAttempt = activeEx?.messages.at(-1)?.kind === "try_first" || live?.kind === "try_first";
  const mode: Mode = hintOnly ? "hint" : tryFirst ? "try_first" : "normal";
  const streaming = live !== null && !live.error;
  const lastAnswered = [...all].sort((a, b) => b.created_at.localeCompare(a.created_at))
    .find((e) => e.messages.at(-1)?.kind === "answer");
  const moreTarget = activeEx && activeEx.messages.at(-1)?.kind === "answer" ? activeEx : lastAnswered;

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

  const retry = () => {
    const r = lastReq.current;
    const exId = live?.exchangeId ?? r?.exchangeId ?? null;
    setLive(null);
    if (r) window.setTimeout(() => void send(r.action, exId, r.content), 0);
  };

  const unkeep = (id: string) => {
    muts.unkeep.mutate(id);
    if (undo) window.clearTimeout(undo.timer);
    setUndo({ id, timer: window.setTimeout(() => setUndo(null), 5000) });
  };
  const note = (text: string) => {
    setFlash(text);
    window.setTimeout(() => setFlash(""), 1500);
  };

  const renderExchange = (ex: Exchange, isKept: boolean) => {
    const isLive = live && live.exchangeId === ex.id;
    const lastAnswerIdx = ex.messages.map((m) => m.kind).lastIndexOf("answer");
    return (
      <article key={ex.id} className={isKept ? "exchange" : "exchange recent"} aria-label={isKept ? "Kept question" : "Temporary doubt"}>
        <button
          className={isKept ? "pin on" : "pin"}
          aria-pressed={isKept}
          aria-label={isKept ? "Un-keep this question" : "Keep this question"}
          title={isKept ? "Kept — click to un-keep" : "Keep"}
          onClick={() => (isKept ? unkeep(ex.id) : muts.keep.mutate(ex.id))}
        >
          {PIN}
        </button>
        {ex.messages.map((m, i) => (
          <div key={i} className="bubble-wrap">
            <Bubble m={m} />
            {i === lastAnswerIdx && !isLive && (
              <div className="answer-actions">
                <button className="btn btn-sm" onClick={() => muts.toCard.mutate(ex.id, { onSuccess: () => note("Flashcard added to Practice") })}>Make flashcard</button>
                <button className="btn btn-sm" onClick={() => muts.toNote.mutate(ex.id, { onSuccess: () => note("Pinned as a note") })}>Pin as note</button>
                <button className="btn btn-sm" onClick={() => muts.toNode.mutate(ex.id, { onSuccess: () => note("Added as a child node") })}>Add as child</button>
              </div>
            )}
          </div>
        ))}
        {isLive && live.user && <Bubble m={live.user} />}
        {isLive && <Bubble m={{ role: "assistant", kind: live.kind, content: live.text || "…" }} />}
        {isLive && live.error && <ErrorRow error={live.error} onRetry={retry} onDismiss={() => setLive(null)} />}
        {!isLive && active !== ex.id && ex.messages.at(-1)?.kind !== "try_first" && (
          <button className="link-muted follow-up" onClick={() => setActive(ex.id)}>Follow up</button>
        )}
        {!isLive && active === ex.id && <span className="xsmall muted">Your next message continues this</span>}
        {!isKept && !isLive && userTurns(ex) >= 3 && !declined.has(ex.id) && (
          <div className="keep-nudge row">
            <span className="grow">Keep this?</span>
            <button className="btn btn-sm" onClick={() => muts.keep.mutate(ex.id)}>Keep</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setDeclined(new Set(declined).add(ex.id))}>No</button>
          </div>
        )}
      </article>
    );
  };

  const newLive = live && !all.some((e) => e.id === live.exchangeId);
  const days = recent.length ? Math.max(...recent.map(daysLeft)) : 7;

  return (
    <div className="thread">
      <div className="thread-scroll">
        {thread.isLoading && <p className="muted small">Loading…</p>}
        {kept.length === 0 && recent.length === 0 && !live && (
          <p className="muted small">Ask anything about this topic. Answers come only from your slides.</p>
        )}
        {kept.map((ex) => renderExchange(ex, true))}
        {recent.length > 0 && <h3 className="recent-head xsmall">Temporary · clears in {days} day{days === 1 ? "" : "s"}</h3>}
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
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          if (awaitingAttempt && active) void send("attempt", active);
          else void send("ask", active);
        }}
      >
        <div className="composer-chips row wrap">
          <button type="button" className="chip" aria-pressed={tryFirst && !hintOnly} disabled={hintOnly} onClick={() => setTryFirst(!tryFirst)}>
            Try first: {tryFirst && !hintOnly ? "on" : "off"}
          </button>
          <button type="button" className="chip" aria-pressed={hintOnly} onClick={() => setHintOnly(!hintOnly)}>Hint only</button>
          <div className="more-wrap">
            <button type="button" className="chip" aria-expanded={moreOpen} disabled={!moreTarget || streaming} onClick={() => setMoreOpen(!moreOpen)}>More help ▾</button>
            {moreOpen && moreTarget && (
              <div className="more-menu" role="menu">
                <button type="button" role="menuitem" className="ctx-item" onClick={() => { setMoreOpen(false); void send("why", moreTarget.id, ""); }}>Explain why</button>
                <button type="button" role="menuitem" className="ctx-item" onClick={() => { setMoreOpen(false); void send("example", moreTarget.id, ""); }}>Give example</button>
              </div>
            )}
          </div>
          {active && <button type="button" className="link-muted" onClick={() => setActive(null)}>New question</button>}
        </div>
        <div className="composer-input row">
          <label className="visually-hidden" htmlFor="ask-input">{awaitingAttempt ? "Your attempt" : "Ask about this topic"}</label>
          <textarea
            id="ask-input"
            className="input composer-text"
            value={draft}
            rows={1}
            placeholder={awaitingAttempt ? "What do you think? Give it a try…" : `Ask about ${nodeLabel}…`}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <button type="submit" className="btn btn-primary" disabled={streaming || !draft.trim()}>
            {awaitingAttempt ? "Send" : "Ask"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Bubble({ m }: { m: Message }) {
  const cls = m.role === "user" ? "bubble user" : m.kind === "try_first" ? "bubble ai try" : m.kind === "hint" ? "bubble ai hint" : "bubble ai";
  return (
    <div className={cls}>
      {m.kind === "try_first" && <span className="bubble-label">Try first</span>}
      {m.kind === "hint" && <span className="bubble-label">Hint</span>}
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
