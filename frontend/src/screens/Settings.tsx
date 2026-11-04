import { useEffect, useState } from "react";
import { useOllamaStatus, usePatchSettings, useSettings } from "../api/hooks";
import { errorMessage } from "../api/client";
import type { Theme } from "../api/types";

export function SettingsScreen() {
  const settings = useSettings();
  const ollama = useOllamaStatus();
  const patch = usePatchSettings();
  const [dataDir, setDataDir] = useState("");

  useEffect(() => {
    if (settings.data) setDataDir(settings.data.data_dir);
  }, [settings.data]);

  if (!settings.data) return <div className="content muted">Loading…</div>;
  const s = settings.data;
  const models = ollama.data?.models ?? [];
  const reachable = ollama.data?.status.reachable;

  return (
    <div className="content content-narrow stack settings">
      <div className="page-head"><h1>Settings</h1></div>

      <section className="card stack">
        <h2>Appearance</h2>
        <label className="field">
          <span>Theme</span>
          <select className="select" value={s.theme} onChange={(e) => patch.mutate({ theme: e.target.value as Theme })}>
            <option value="system">Follow system</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </label>
      </section>

      <section className="card stack">
        <h2>Data folder</h2>
        <p className="muted small">Plain files you own. It can live inside Google Drive or OneDrive.</p>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            patch.mutate({ data_dir: dataDir });
          }}
        >
          <input className="input" aria-label="Data folder path" value={dataDir} onChange={(e) => setDataDir(e.target.value)} />
          <button className="btn" type="submit" disabled={dataDir === s.data_dir}>Use folder</button>
        </form>
      </section>

      <section className="card stack">
        <h2>Ollama</h2>
        {ollama.isLoading && <p className="muted">Checking Ollama…</p>}
        {ollama.data && (
          reachable ? (
            <p>Connected <span className="muted mono small">{ollama.data.status.url} · v{ollama.data.status.version}</span></p>
          ) : (
            <div className="banner banner-error">
              <span>{ollama.data.status.error || "Ollama isn't running."}</span>
              <span className="spacer" />
              <a className="btn btn-sm" href="https://ollama.com/download" target="_blank" rel="noreferrer">Install Ollama</a>
              <button className="btn btn-sm" onClick={() => void ollama.refetch()}>Retry</button>
            </div>
          )
        )}
        {ollama.data?.json_warnings.map((m) => (
          <p key={m} className="banner banner-error">“{m}” keeps returning broken JSON. Try a larger model for this slot.</p>
        ))}
        <ModelSlot label="Map model (heavy, used rarely)" value={s.map_model} models={models} onChange={(v) => patch.mutate({ map_model: v })} />
        <ModelSlot label="Study model (light, used often)" value={s.study_model} models={models} onChange={(v) => patch.mutate({ study_model: v })} />
      </section>

      <section className="card stack">
        <h2>Study</h2>
        <label className="row">
          <input type="checkbox" checked={s.keep_all_questions} onChange={(e) => patch.mutate({ keep_all_questions: e.target.checked })} />
          Keep all questions by default
        </label>
        <label className="row">
          <input type="checkbox" checked={s.usage_log} onChange={(e) => patch.mutate({ usage_log: e.target.checked })} />
          Local usage log (feature counts in your data folder; never sent anywhere)
        </label>
      </section>

      {patch.isError && <p className="banner banner-error">{errorMessage(patch.error)}</p>}
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
          <option key={m.name} value={m.name}>
            {m.name}{m.parameter_size ? ` · ${m.parameter_size}` : ""}{m.vision ? " · vision" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
