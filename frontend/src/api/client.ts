export class ApiError extends Error {
  status: number;
  kind: string;
  constructor(message: string, status: number, kind = "") {
    super(message);
    this.status = status;
    this.kind = kind;
  }
}

function detailToMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join("; ");
  }
  return "Something went wrong.";
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const opts: RequestInit = { ...rest, headers: { ...(headers ?? {}) } };
  if (json !== undefined) {
    opts.body = JSON.stringify(json);
    (opts.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, opts);
  } catch {
    throw new ApiError("Can't reach the Nodebook server. Is it still running?", 0);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body: unknown = text ? safeJson(text) : undefined;
  if (!res.ok) {
    const b = (body ?? {}) as { detail?: unknown; kind?: string };
    throw new ApiError(detailToMessage(b.detail ?? res.statusText), res.status, b.kind ?? "");
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
