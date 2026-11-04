import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/client";
import { useJob, useOllamaStatus, usePatchSettings, useSettings } from "../api/hooks";
import { usePull, useRecommended, useRefreshModels, useTestMap, type RecModel } from "../api/system";

/** Recommended models per slot, one-click pull, any installed model selectable, "Test on my slides" (SPEC §5.15). */
export function ModelsPanel() {
  const rec = useRecommended();
  const settings = useSettings();
  const ollama = useOllamaStatus();
  const patch = usePatchSettings();
  const installed = ollama.data?.models ?? [];
  if (!rec.data || !settings.data) return <p className="muted">Checking your computer…</p>;
  const s = settings.data;
  return (
    <div className="stack">
      <p className="small text-2">This computer has <strong className="mono">{rec.data.ram_gb} GB</strong> RAM ({rec.data.tier_label}).</p>
      <Slot title="Map model" sub="Heavy, used rarely — builds maps from your decks." recs={rec.data.map}
        value={s.map_model} installed={installed} onUse={(n) => patch.mutate({ map_model: n })} />
      <Slot title="Study model" sub="Light, used often — answers, grading, generating." recs={rec.data.study}
        value={s.study_model} installed={installed} onUse={(n) => patch.mutate({ study_model: n })} />
      {ollama.data?.json_warnings.map((m) => (
        <p key={m} className="banner banner-error small">“{m}” keeps returning broken JSON. Try a larger model for this slot.</p>
      ))}
      <TestOnSlides />
    </div>
  );
}

function Slot({ title, sub, recs, value, installed, onUse }: {
  title: string; sub: string; recs: RecModel[]; value: string | null;
  installed: { name: string; vision: boolean; parameter_size: string }[]; onUse: (name: string) => void;
}) {
  const known = installed.some((m) => m.name === value);
  return (
    <section className="model-slot stack">
      <div><h3>{title}</h3><p className="small text-2">{sub}</p></div>
      {recs.map((m, i) => <RecRow key={m.name} m={m} recommended={i === 0} active={value === m.name || value === `${m.name}:latest`} onUse={onUse} />)}
      <label className="field">
        <span>Or any installed model</span>
        <select className="select" value={value ?? ""} onChange={(e) => onUse(e.target.value)}>
          <option value="" disabled>Choose a model…</option>
          {value && !known && <option value={value}>{value} (not installed)</option>}
          {installed.map((m) => (
            <option key={m.name} value={m.name}>{m.name}{m.parameter_size ? ` · ${m.parameter_size}` : ""}{m.vision ? " · vision" : ""}</option>
          ))}
        </select>
      </label>
    </section>
  );
}

function RecRow({ m, recommended, active, onUse }: { m: RecModel; recommended: boolean; active: boolean; onUse: (n: string) => void }) {
  const pull = usePull();
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJob(jobId);
  const refresh = useRefreshModels();
  const doneRef = useRef(false);
  useEffect(() => {
    if (job.data?.state === "done" && !doneRef.current) {
      doneRef.current = true;
      refresh();
      onUse(m.name);
    }
  }, [job.data?.state, m.name, onUse, refresh]);
  const pulling = job.data && (job.data.state === "queued" || job.data.state === "running");
  const pct = Math.round((job.data?.progress ?? 0) * 100);
  return (
    <div className={active ? "rec-row active" : "rec-row"}>
      <div className="grow stack-tight">
        <div className="row wrap">
          <span className="mono">{m.name}</span>
          {recommended && <span className="badge">Recommended</span>}
          {m.vision && <span className="badge badge-2">vision</span>}
          <span className="small muted mono">{m.size_gb} GB</span>
        </div>
        <span className="small text-2">{m.why}</span>
        {pulling && (
          <div className="job-progress">
            <div className="progress-track" aria-hidden="true"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
            <span className="small muted">{job.data?.message} <span className="mono">{pct}%</span></span>
          </div>
        )}
        {job.data?.state === "failed" && <span className="small error-text">{job.data.error}</span>}
        {pull.isError && <span className="small error-text">{errorMessage(pull.error)}</span>}
      </div>
      {m.installed || job.data?.state === "done" ? (
        active ? <span className="small text-2">In use</span> : <button className="btn btn-sm" onClick={() => onUse(m.name)}>Use</button>
      ) : (
        <button className="btn btn-sm btn-primary" disabled={Boolean(pulling) || pull.isPending}
          onClick={() => { doneRef.current = false; pull.mutate(m.name, { onSuccess: (j) => setJobId(j.id) }); }}>
          {pulling ? "Downloading…" : "Download"}
        </button>
      )}
    </div>
  );
}

function TestOnSlides() {
  const test = useTestMap();
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJob(jobId);
  const input = useRef<HTMLInputElement>(null);
  const r = job.data?.result as { outline?: string[]; nodes?: number; uncovered?: number[]; fallback?: boolean; seconds?: number; model?: string } | null | undefined;
  const running = job.data && (job.data.state === "queued" || job.data.state === "running");
  return (
    <section className="model-slot stack">
      <div className="row">
        <div className="grow"><h3>Test on my slides</h3><p className="small text-2">Builds a map from a deck with the map model. Nothing is saved.</p></div>
        <button className="btn btn-sm" disabled={Boolean(running)} onClick={() => input.current?.click()}>{running ? "Testing…" : "Choose a deck"}</button>
        <input ref={input} type="file" accept=".pdf,.pptx" className="visually-hidden" tabIndex={-1} aria-hidden="true"
          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) test.mutate(f, { onSuccess: (j) => setJobId(j.id) }); }} />
      </div>
      {running && <p className="small muted">{job.data?.message || "Starting…"} <span className="mono">{Math.round((job.data?.progress ?? 0) * 100)}%</span></p>}
      {(test.isError || job.data?.state === "failed") && <p className="banner banner-error small">{test.isError ? errorMessage(test.error) : job.data?.error}</p>}
      {r?.outline && (
        <div className="stack-tight">
          <p className="small text-2"><span className="mono">{r.model}</span> · {r.nodes} nodes in {r.seconds}s{r.uncovered?.length ? ` · ${r.uncovered.length} slides not covered` : ""}{r.fallback ? " · fell back to a flat map (try a larger model)" : ""}</p>
          <pre className="outline">{r.outline.join("\n")}</pre>
        </div>
      )}
    </section>
  );
}
