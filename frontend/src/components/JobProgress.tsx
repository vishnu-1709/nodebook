import { useJob } from "../api/hooks";

export function JobProgress({ jobId, fallbackText = "Waiting…" }: { jobId: string | null; fallbackText?: string }) {
  const job = useJob(jobId);
  const pct = Math.round((job.data?.progress ?? 0) * 100);
  return (
    <div className="job-progress" role="status" aria-live="polite">
      <div className="progress-track" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="small muted">{job.data?.message || fallbackText} <span className="mono">{pct}%</span></span>
    </div>
  );
}
