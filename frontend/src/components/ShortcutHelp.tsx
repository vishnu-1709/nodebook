import { SHORTCUTS } from "../app/shortcuts";
import { Modal } from "./Modal";

export function ShortcutHelp({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="Keyboard shortcuts" onClose={onClose}>
      <table className="shortcut-table">
        <tbody>
          {SHORTCUTS.map((s) => (
            <tr key={s.key}>
              <td><span className="kbd">{s.key}</span></td>
              <td>{s.label}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">Shortcuts are off while you type in a text box.</p>
    </Modal>
  );
}
