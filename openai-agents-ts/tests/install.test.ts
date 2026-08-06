import { describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

describe("customer install", () => {
  it("ships built dist and exports RunCollector", async () => {
    const dist = resolve(import.meta.dirname, "../dist/index.js");
    expect(existsSync(dist)).toBe(true);
    const mod = await import("../dist/index.js");
    expect(typeof mod.RunCollector).toBe("function");
    expect(typeof mod.collectorToWirePayload).toBe("function");
  });
});
