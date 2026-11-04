import { describe, expect, it } from "vitest";
import type { MapDoc } from "../api/types";
import { formatSlideList, nodePath, toMindElixir } from "./mapData";

const node = (id: string, label: string, parent: string | null, children: string[] = []) => ({
  id, label, parent_id: parent, children, sources: [{ source_id: "S", slide: 1 }],
  status: "not_started" as const, status_mode: "manual" as const, last_studied_at: null, origin: "ai" as const, collapsed: false,
});

const doc: MapDoc = {
  lecture_id: "L",
  root_id: "r",
  nodes: {
    r: node("r", "Root", null, ["a", "b"]),
    a: { ...node("a", "A", "r", ["c"]), status: "confused" },
    b: node("b", "B", "r"),
    c: node("c", "C", "a"),
  },
};

describe("mapData", () => {
  it("keeps ids and structure", () => {
    const t = toMindElixir(doc, { a: 2 });
    expect(t.id).toBe("r");
    expect(t.children?.map((c) => c.id)).toEqual(["a", "b"]);
    expect(t.children?.[0]?.children?.[0]?.id).toBe("c");
    const tags = t.children?.[0]?.tags as { text: string; className: string }[];
    expect(tags[0]?.text).toBe("Confused");
    expect(tags[1]).toEqual({ text: "2", className: "me-badge" });
  });

  it("builds a breadcrumb path", () => {
    expect(nodePath(doc, "c")).toEqual(["Root", "A", "C"]);
  });

  it("formats slide lists", () => {
    expect(formatSlideList([21, 14])).toBe("14 and 21");
    expect(formatSlideList([3, 1, 2])).toBe("1, 2 and 3");
  });
});

describe("structure round trip", () => {
  it("mind-elixir tree → payload matches stored structure", async () => {
    const { fromMindElixir, treeOf, siblingsOf } = await import("./mapData");
    const t = toMindElixir(doc);
    expect(fromMindElixir(t)).toEqual(treeOf(doc));
    expect(siblingsOf(doc, "a")).toEqual([{ id: "b", label: "B" }]);
    expect(siblingsOf(doc, "r")).toEqual([]);
  });
});
