import { describe, expect, it } from "vitest";
import { initials, isCollapsed, screenType } from "./sidebar";

describe("sidebar", () => {
  it("maps routes to screen types", () => {
    expect(screenType("/")).toBe("today");
    expect(screenType("/course/A")).toBe("course");
    expect(screenType("/course/A/lecture/B")).toBe("lecture");
    expect(screenType("/settings")).toBe("settings");
  });
  it("lecture map defaults to collapsed, others expanded, choice remembered", () => {
    expect(isCollapsed({}, "lecture")).toBe(true);
    expect(isCollapsed({}, "today")).toBe(false);
    expect(isCollapsed({ lecture: false }, "lecture")).toBe(false);
    expect(isCollapsed({ today: true }, "today")).toBe(true);
  });
  it("makes course initials", () => {
    expect(initials("Intro to Data Science")).toBe("ID");
    expect(initials("Linear Algebra")).toBe("LA");
    expect(initials("GATE DA prep")).toBe("GD");
    expect(initials("x")).toBe("X");
  });
});
