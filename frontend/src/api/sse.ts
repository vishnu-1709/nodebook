/** POST + read a text/event-stream body. Calls onEvent for every `data:` JSON line. */
export async function postSSE(
  path: string,
  body: unknown,
  onEvent: (e: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const j = (await res.json()) as { detail?: string };
      if (j.detail) detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || "Request failed");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    buf = drain(buf, onEvent);
  }
  drain(buf + "\n\n", onEvent);
}

export function drain(buf: string, onEvent: (e: Record<string, unknown>) => void): string {
  let idx: number;
  while ((idx = buf.indexOf("\n\n")) >= 0) {
    const chunk = buf.slice(0, idx);
    buf = buf.slice(idx + 2);
    for (const line of chunk.split("\n")) {
      if (line.startsWith("data: ")) {
        try {
          onEvent(JSON.parse(line.slice(6)) as Record<string, unknown>);
        } catch {
          /* ignore malformed */
        }
      }
    }
  }
  return buf;
}
