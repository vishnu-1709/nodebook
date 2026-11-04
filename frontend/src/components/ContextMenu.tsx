import { useEffect, useRef, type ReactNode } from "react";

export interface MenuItem {
  label: string;
  onSelect?: () => void;
  disabled?: boolean;
  hint?: string;
  submenu?: MenuItem[];
  separator?: boolean;
  danger?: boolean;
}

interface Props {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}

export function ContextMenu({ x, y, items, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>("button:not(:disabled)")?.focus();
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const btns = Array.from(ref.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []);
        const i = btns.indexOf(document.activeElement as HTMLButtonElement);
        const next = btns[(i + (e.key === "ArrowDown" ? 1 : -1) + btns.length) % btns.length];
        next?.focus();
      }
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey, true);
    };
  }, [onClose]);

  const left = Math.min(x, window.innerWidth - 260);
  const top = Math.min(y, window.innerHeight - 40 * items.length - 20);
  return (
    <div ref={ref} className="ctx-menu" role="menu" style={{ left, top }}>
      {items.map((it, i) => <Item key={i} it={it} onClose={onClose} />)}
    </div>
  );
}

function Item({ it, onClose }: { it: MenuItem; onClose: () => void }): ReactNode {
  if (it.separator) return <div className="ctx-sep" role="separator" />;
  if (it.submenu) {
    return (
      <div className="ctx-sub">
        <div className="ctx-sub-label small muted">{it.label}</div>
        {it.submenu.length === 0 && <div className="ctx-empty small muted">Nothing here</div>}
        {it.submenu.map((s, i) => <Item key={i} it={s} onClose={onClose} />)}
      </div>
    );
  }
  return (
    <button
      role="menuitem"
      className={it.danger ? "ctx-item danger" : "ctx-item"}
      disabled={it.disabled}
      onClick={() => {
        onClose();
        it.onSelect?.();
      }}
    >
      <span>{it.label}</span>
      {it.hint && <span className="hint">{it.hint}</span>}
    </button>
  );
}
