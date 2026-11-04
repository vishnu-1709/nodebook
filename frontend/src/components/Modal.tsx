import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
  /** Small popover near the top, no title bar (UI.md §3.9). */
  popover?: boolean;
}

// Stack of open modals: Esc closes only the top one; global shortcuts pause while any is open.
const stack: number[] = [];
let nextId = 1;
export function anyModalOpen(): boolean {
  return stack.length > 0;
}

/** Register a layer in the modal stack: Esc closes the top one; global shortcuts pause. */
export function useModalLayer(onClose: () => void): void {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const id = nextId++;
    stack.push(id);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && stack[stack.length - 1] === id) {
        e.preventDefault();
        e.stopImmediatePropagation();
        closeRef.current();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      const i = stack.indexOf(id);
      if (i >= 0) stack.splice(i, 1);
    };
  }, []);
}

export function Modal({ title, onClose, children, wide, popover }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useModalLayer(onClose);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const first =
      ref.current?.querySelector<HTMLElement>("input:not([type=checkbox]):not([readonly]), textarea:not([readonly]), select") ??
      ref.current?.querySelector<HTMLElement>(".modal-body button, button.btn-primary") ??
      ref.current?.querySelector<HTMLElement>("button");
    first?.focus();
    return () => prev?.focus?.();
  }, []);
  if (popover) {
    return (
      <div className="popover-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
        <div ref={ref} className="popover" role="dialog" aria-modal="true" aria-label={title}>{children}</div>
      </div>
    );
  }
  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} className={wide ? "modal modal-wide" : "modal"} role="dialog" aria-modal="true" aria-label={title}>
        <div className="row">
          <h2>{title}</h2>
          <span className="spacer" />
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">
            Close <span className="hint">Esc</span>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
