import { MAP_KEYS, SHORTCUTS } from "../app/shortcuts";
import { Modal } from "./Modal";

export function ShortcutHelp({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="Keyboard shortcuts" onClose={onClose}>
      <h3>Everywhere</h3>
      <table className="shortcut-table">
        <tbody>
          {SHORTCUTS.map((s) => (
            <tr key={s.key}><td><span className="hint">{s.key}</span></td><td>{s.label}</td></tr>
          ))}
        </tbody>
      </table>
      <h3>Mind map</h3>
      <table className="shortcut-table">
        <tbody>
          {MAP_KEYS.map((s) => (
            <tr key={s.key}><td><span className="hint">{s.key}</span></td><td>{s.label}</td></tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">Single-letter shortcuts are off while you type in a text box.</p>
    </Modal>
  );
}
