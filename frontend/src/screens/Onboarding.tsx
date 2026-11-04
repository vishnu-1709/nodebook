import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useOllamaStatus, usePatchSettings, useSettings } from "../api/hooks";
import { ModelsPanel } from "../components/ModelsPanel";

const STEPS = ["Data folder", "Ollama", "Models"];

/** First-run wizard (SPEC §5.15, UI.md §3.8): data folder → Ollama check → models. */
export function Onboarding() {
  const settings = useSettings();
  const ollama = useOllamaStatus();
  const patch = usePatchSettings();
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [dir, setDir] = useState("");
  useEffect(() => { if (settings.data && !dir) setDir(settings.data.data_dir); }, [settings.data, dir]);

  const up = ollama.data?.status.reachable;
  const finish = () => patch.mutate({ onboarded: true }, { onSuccess: () => nav("/") });

  return (
    <div className="onboard">
      <div className="card onboard-card stack">
        <div className="wordmark onboard-mark">Nodebook</div>
        <ol className="steps" aria-label="Setup steps">
          {STEPS.map((s, i) => (
            <li key={s} className={i === step ? "step on" : i < step ? "step done" : "step"} aria-current={i === step ? "step" : undefined}>
              <span className="step-num mono">{i < step ? "✓" : i + 1}</span>{s}
            </li>
          ))}
        </ol>

        {step === 0 && (
          <form className="stack" onSubmit={(e) => { e.preventDefault(); patch.mutate({ data_dir: dir }, { onSuccess: () => setStep(1) }); }}>
            <h2>Where should Nodebook keep your files?</h2>
            <p className="text-2 small">Plain files you own. The folder can sit inside Google Drive or OneDrive.</p>
            <label className="field"><span>Data folder</span>
              <input className="input mono" value={dir} onChange={(e) => setDir(e.target.value)} />
            </label>
            {patch.isError && <p className="banner banner-error small">{errorMessage(patch.error)}</p>}
            <div className="row"><span className="spacer" /><button className="btn btn-primary" disabled={!dir.trim() || patch.isPending}>Continue</button></div>
          </form>
        )}

        {step === 1 && (
          <div className="stack">
            <h2>Connect to Ollama</h2>
            <p className="text-2 small">Nodebook uses a local AI model through Ollama. Nothing leaves your computer.</p>
            {ollama.isLoading && <p className="muted">Checking…</p>}
            {ollama.data && (up ? (
              <p className="row"><span className="ollama-dot" aria-hidden="true" /> Ollama is running <span className="muted mono small">v{ollama.data.status.version}</span></p>
            ) : (
              <div className="banner banner-error">
                <span className="grow">{ollama.data.status.error || "Ollama isn't running."}</span>
                <a className="btn btn-sm" href="https://ollama.com/download" target="_blank" rel="noreferrer">Install Ollama</a>
                <button className="btn btn-sm" onClick={() => void ollama.refetch()}>Retry</button>
              </div>
            ))}
            <div className="row">
              <button className="btn btn-ghost" onClick={() => setStep(0)}>Back</button>
              <span className="spacer" />
              {!up && <button className="link-muted" onClick={() => setStep(2)}>Skip for now</button>}
              <button className="btn btn-primary" disabled={!up} onClick={() => setStep(2)}>Continue</button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="stack">
            <h2>Pick your models</h2>
            {up ? <ModelsPanel /> : <p className="text-2 small">Start Ollama to download and pick models. You can do this later in Settings → AI models.</p>}
            <div className="row">
              <button className="btn btn-ghost" onClick={() => setStep(1)}>Back</button>
              <span className="spacer" />
              <button className="btn btn-primary" onClick={finish} disabled={patch.isPending}>Start using Nodebook</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
