import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { useOllamaStatus, usePatchSettings, useSettings } from "../api/hooks";
import type { Theme } from "../api/types";
import { PageHead } from "../components/PageHead";

type Section = "general" | "models" | "study" | "pomodoro" | "data";
const SECTIONS: { id: Section; label: string }[] = [
  { id: "general", label: "General" },
  { id: "models", label: "AI models" },
  { id: "study", label: "Study" },
  { id: "pomodoro", label: "Pomodoro" },
  { id: "data", label: "Data" },
];

export function SettingsScreen() {
  const settings = useSettings();
  const ollama = useOllamaStatus();
  const patch = usePatchSettings();
  const [section, setSection] = useState<Section>("general");
  const [dataDir, setDataDir] = useState("");

  useEffect(() => {
    if (settings.data) setDataDir(settings.data.data_dir);
  }, [settings.data]);

  if (!settings.data) return <div className="content muted">Loading…</div>;
  const s = settings.data;
  const models = ollama.data?.models ?? [];
  const reachable = ollama.data?.status.reachable;

  return (
    <div className="content content-narrow">
      <PageHead title="Settings" />
      <div className="settings-layout">
        <nav className="settings-nav" aria-label="Settings sections">
          {SECTIONS.map((x) => (
            <button key={x.id} className={section === x.id ? "nav-link active link-reset" : "nav-link link-reset"} aria-current={section === x.id} onClick={() => setSection(x.id)}>
              {x.label}
            </button>
          ))}
        </nav>
        <section className="card stack settings-form">
          {section === "general" && (
            <>
              <h2>General</h2>
              <label className="field">
                <span>Theme</span>
                <select className="select" value={s.theme} onChange={(e) => patch.mutate({ theme: e.target.value as Theme })}>
                  <option value="system">Follow system</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </label>
            </>
          )}
          {section === "models" && (
            <>
              <h2>AI models</h2>
              {ollama.isLoading && <p className="muted">Checking Ollama…</p>}
              {ollama.data && (reachable ? (
                <p className="row"><span className="ollama-dot" aria-hidden="true" /> Ollama running <span className="muted mono small">{ollama.data.status.url} · v{ollama.data.status.version}</span></p>
              ) : (
                <div className="banner banner-error">
                  <span className="grow">{ollama.data.status.error || "Ollama isn't running."}</span>
                  <a className="btn btn-sm" href="https://ollama.com/download" target="_blank" rel="noreferrer">Install Ollama</a>
                  <button className="btn btn-sm" onClick={() => void ollama.refetch()}>Retry</button>
                </div>
              ))}
              {ollama.data?.json_warnings.map((m) => (
                <p key={m} className="banner banner-error">“{m}” keeps returning broken JSON. Try a larger model for this slot.</p>
              ))}
              <ModelSlot label="Map model (heavy, used rarely)" value={s.map_model} models={models} onChange={(v) => patch.mutate({ map_model: v })} />
              <ModelSlot label="Study model (light, used often)" value={s.study_model} models={models} onChange={(v) => patch.mutate({ study_model: v })} />
            </>
          )}
          {section === "study" && (
            <>
              <h2>Study</h2>
              <label className="row">
                <input type="checkbox" checked={s.keep_all_questions} onChange={(e) => patch.mutate({ keep_all_questions: e.target.checked })} />
                Keep all questions by default
              </label>
              <p className="small muted">Off: new questions are temporary and clear after 7 days unless you keep them.</p>
            </>
          )}
          {section === "pomodoro" && (
            <>
              <h2>Pomodoro</h2>
              <p className="small muted">Presets offered in the timer popover.</p>
              {s.pomodoro_presets.map((p, i) => (
                <div key={i} className="row">
                  <label className="field"><span>Focus (min)</span>
                    <input className="input" type="number" min={1} max={180} value={p.work_min}
                      onChange={(e) => patch.mutate({ pomodoro_presets: s.pomodoro_presets.map((x, j) => (j === i ? { ...x, work_min: Number(e.target.value) || 1 } : x)) })} />
                  </label>
                  <label className="field"><span>Break (min)</span>
                    <input className="input" type="number" min={1} max={60} value={p.break_min}
                      onChange={(e) => patch.mutate({ pomodoro_presets: s.pomodoro_presets.map((x, j) => (j === i ? { ...x, break_min: Number(e.target.value) || 1 } : x)) })} />
                  </label>
                </div>
              ))}
            </>
          )}
          {section === "data" && (
            <>
              <h2>Data</h2>
              <p className="muted small">Plain files you own. The folder can live inside Google Drive or OneDrive.</p>
              <form className="row" onSubmit={(e) => { e.preventDefault(); patch.mutate({ data_dir: dataDir }); }}>
                <input className="input" aria-label="Data folder path" value={dataDir} onChange={(e) => setDataDir(e.target.value)} />
                <button className="btn" type="submit" disabled={dataDir === s.data_dir}>Use folder</button>
              </form>
              <label className="row">
                <input type="checkbox" checked={s.usage_log} onChange={(e) => patch.mutate({ usage_log: e.target.checked })} />
                Local usage log (feature counts in your data folder; never shown or sent anywhere)
              </label>
            </>
          )}
          {patch.isError && <p className="banner banner-error">{errorMessage(patch.error)}</p>}
        </section>
      </div>
    </div>
  );
}

function ModelSlot(props: {
  label: string;
  value: string | null;
  models: { name: string; vision: boolean; parameter_size: string }[];
  onChange: (v: string) => void;
}) {
  const known = props.models.some((m) => m.name === props.value);
  return (
    <label className="field">
      <span>{props.label}</span>
      <select className="select" value={props.value ?? ""} onChange={(e) => props.onChange(e.target.value)}>
        <option value="" disabled>Choose a model…</option>
        {props.value && !known && <option value={props.value}>{props.value} (not installed)</option>}
        {props.models.map((m) => (
          <option key={m.name} value={m.name}>{m.name}{m.parameter_size ? ` · ${m.parameter_size}` : ""}{m.vision ? " · vision" : ""}</option>
        ))}
      </select>
    </label>
  );
}
