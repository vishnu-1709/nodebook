import { describe, expect, it } from "vitest";
import { actionFor, isTypingTarget } from "./shortcuts";

describe("shortcuts", () => {
  it("maps keys to actions", () => {
    expect(actionFor({ key: "n" })).toBe("quick_note");
    expect(actionFor({ key: "G" })).toBe("generate");
    expect(actionFor({ key: "?" })).toBe("help");
    expect(actionFor({ key: "x" })).toBeNull();
  });

  it("is disabled while typing, except Esc", () => {
    const input = document.createElement("input");
    const ta = document.createElement("textarea");
    const div = document.createElement("div");
    div.setAttribute("contenteditable", "true");
    for (const el of [input, ta, div]) {
      expect(isTypingTarget(el)).toBe(true);
      expect(actionFor({ key: "n", target: el })).toBeNull();
      expect(actionFor({ key: "Escape", target: el })).toBe("escape");
    }
    expect(actionFor({ key: "n", target: document.createElement("button") })).toBe("quick_note");
  });

  it("Ctrl/Cmd+B toggles the sidebar, not while typing", () => {
    expect(actionFor({ key: "b", ctrlKey: true })).toBe("toggle_sidebar");
    expect(actionFor({ key: "B", metaKey: true })).toBe("toggle_sidebar");
    expect(actionFor({ key: "b", ctrlKey: true, target: document.createElement("textarea") })).toBeNull();
  });

  it("ignores modified keys", () => {
    expect(actionFor({ key: "r", ctrlKey: true })).toBeNull();
    expect(actionFor({ key: "n", metaKey: true })).toBeNull();
  });
});
