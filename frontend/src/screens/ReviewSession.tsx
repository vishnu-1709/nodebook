import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useCourse } from "../api/hooks";
import { useRate, useReviewQueue, type ReviewItem } from "../api/review";
import type { SlideRef } from "../api/types";
import { isTypingTarget } from "../app/shortcuts";
import { useModalLayer } from "../components/Modal";
import { PomodoroChip } from "../components/PomodoroChip";
import { SlidePreview } from "../components/SlidePreview";

const RATINGS: { n: 1 | 2 | 3 | 4; label: string; cls: string }[] = [
  { n: 1, label: "Again", cls: "rate-again" },
  { n: 2, label: "Hard", cls: "" },
  { n: 3, label: "Good", cls: "rate-good" },
  { n: 4, label: "Easy", cls: "" },
];
const STATUS_TEXT: Record<string, string> = { confused: "Marked confused", revising: "Revising", got_it: "Got it" };

/** Review session — UI.md §3.6, docs/ui/review-session.png. No sidebar; one item, nothing else. */
export function ReviewSession() {
  const [params] = useSearchParams();
  const courseId = params.get("course");
  const lectureId = params.get("lecture");
  const nav = useNavigate();
  const end = () => nav(courseId ? `/review?course=${courseId}` : "/review");
  useModalLayer(end);
  const q = useReviewQueue(courseId, lectureId);
  const course = useCourse(courseId ?? undefined);
  const rate = useRate();
  const [i, setI] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [answer, setAnswer] = useState("");
  const [preview, setPreview] = useState<SlideRef[] | null>(null);
  const shownAt = useRef(Date.now());

  const items = q.data?.items ?? [];
  const cur: ReviewItem | undefined = items[i];
  const total = items.length;
  const cards = items.filter((x) => x.item.type === "card").length;
  const questions = total - cards;
  const done = q.isSuccess && i >= total;

  useEffect(() => { shownAt.current = Date.now(); setFlipped(false); setAnswer(""); }, [i]);

  const doRate = (n: 1 | 2 | 3 | 4) => {
    if (!cur || !flipped || rate.isPending) return;
    rate.mutate(
      { course_id: cur.course_id, lecture_id: cur.lecture_id, item_id: cur.item.id, rating: n, duration_ms: Date.now() - shownAt.current },
      { onSuccess: () => setI((x) => x + 1) },
    );
  };
  const flip = () => { if (cur && (cur.item.type === "card" || answer.trim())) setFlipped(true); };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (isTypingTarget(e.target)) {
        if (e.key === "Enter" && !e.shiftKey && !flipped) { e.preventDefault(); flip(); }
        return;
      }
      if (e.key === " ") { e.preventDefault(); flip(); }
      if (["1", "2", "3", "4"].includes(e.key)) { e.preventDefault(); doRate(Number(e.key) as 1 | 2 | 3 | 4); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const src = cur?.item.origin.ref?.match(/slide (\d+)/i);
  const nodeLink = cur?.lecture_id && cur.item.node_id ? `/course/${cur.course_id}/lecture/${cur.lecture_id}?node=${cur.item.node_id}` : null;

  return (
    <div className="fullscreen review-screen" role="dialog" aria-modal="true" aria-label="Review session">
      <header className="review-head">
        <button className="btn btn-ghost btn-sm" onClick={end}>✕ End session</button>
        <span className="spacer" />
        <span className="small text-2">{course.data?.course.name ?? "All courses"} · {cards} card{cards === 1 ? "" : "s"} + {questions} saved question{questions === 1 ? "" : "s"}</span>
        <span className="mono">{Math.min(i + 1, total)} / {total}</span>
        <PomodoroChip />
      </header>
      <div className="review-progress" aria-hidden="true"><div style={{ width: `${total ? (Math.min(i, total) / total) * 100 : 0}%` }} /></div>

      <main className="review-main">
        {q.isLoading && <p className="muted">Loading your queue…</p>}
        {q.isError && <p className="banner banner-error">{errorMessage(q.error)}</p>}
        {q.isSuccess && total === 0 && (
          <div className="review-card stack">
            <h2>Nothing due right now.</h2>
            <p className="text-2">Save questions from Generate or make flashcards on a topic, and they'll come back here.</p>
            <div><button className="btn btn-primary" onClick={end}>Back</button></div>
          </div>
        )}
        {done && total > 0 && (
          <div className="review-card stack">
            <h2>Session done · {total} reviewed</h2>
            <p className="text-2">Next items come back when they're due.</p>
            <div><button className="btn btn-primary" onClick={end}>Back</button></div>
          </div>
        )}
        {cur && !done && (
          <>
            <article className="review-card">
              <div className="row review-meta">
                <span className="small muted">{[cur.lecture_title, ...cur.node_path].filter(Boolean).join(" › ")}</span>
                <span className="spacer" />
                {cur.node_status && STATUS_TEXT[cur.node_status] && <span className={`small status-text-${cur.node_status}`}>{STATUS_TEXT[cur.node_status]}</span>}
              </div>
              <h1 className="review-q">{cur.item.front}</h1>
              {cur.item.type === "question" && !flipped && (
                <div className="stack">
                  <label className="visually-hidden" htmlFor="review-answer">Your answer</label>
                  <textarea id="review-answer" className="textarea" rows={3} value={answer} autoFocus
                    onChange={(e) => setAnswer(e.target.value)} placeholder="Answer first, then press Enter to see the worked answer" />
                </div>
              )}
              {flipped && (
                <>
                  <hr className="review-divider" />
                  {cur.item.type === "question" && answer && <p className="small text-2">Your answer: {answer}</p>}
                  <p className="review-a">{cur.item.back || "(no answer saved)"}</p>
                  {cur.item.answer_status === "ai_unverified" && cur.item.type === "question" && <span className="tag-ai">AI answer · check it</span>}
                </>
              )}
              <div className="row review-links">
                {nodeLink && <Link className="small" to={nodeLink}>Open node</Link>}
                {src && cur.item.origin.source_ids[0] && (
                  <button className="link-btn" onClick={() => setPreview([{ source_id: cur.item.origin.source_ids[0]!, slide: Number(src[1]) }])}>See slide {src[1]}</button>
                )}
              </div>
            </article>
            {!flipped ? (
              <button className="btn review-flip" onClick={flip} disabled={cur.item.type === "question" && !answer.trim()}>
                {cur.item.type === "question" ? "Show answer" : "Show answer"} <span className="kbd">space</span>
              </button>
            ) : (
              <div className="rating-row" role="group" aria-label="How well did you remember?">
                {RATINGS.map((r) => (
                  <button key={r.n} className={`btn rating ${r.cls}`} onClick={() => doRate(r.n)} disabled={rate.isPending}>
                    <span className="rating-label">{r.label}</span>
                    <span className="mono xsmall">{cur.intervals[String(r.n) as "1"]}</span>
                  </button>
                ))}
              </div>
            )}
            {rate.isError && <p className="banner banner-error small">{errorMessage(rate.error)}</p>}
            <p className="hint center">1 2 3 4 · space: flip</p>
          </>
        )}
      </main>
      {preview && cur && <SlidePreview courseId={cur.course_id} refs={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}
