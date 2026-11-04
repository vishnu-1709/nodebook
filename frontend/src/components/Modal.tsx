import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}

export function Modal({ title, onClose, children, wide }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>("input, textarea, select, button");
    first?.focus();
    return () => prev?.focus?.();
  }, []);
  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} className={wide ? "modal modal-wide" : "modal"} role="dialog" aria-modal="true" aria-label={title}>
        <div className="row">
          <h2>{title}</h2>
          <span className="spacer" />
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">
            Close <span className="kbd">Esc</span>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
