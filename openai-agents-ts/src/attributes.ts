import { RunCollector } from "./collector.js";

export function addInteractionAttributes(attributes: Record<string, unknown>): void {
  const collector = RunCollector.current();
  if (!collector || !attributes) return;
  collector.mergeRunAttributes(attributes);
}

export function addSpanAttributes(attributes: Record<string, unknown>): void {
  const collector = RunCollector.current();
  if (!collector || !attributes) return;
  collector.mergePendingSpanAttributes(attributes);
}

export function emitSignal(
  name: string,
  opts: { kind?: "context" | "trigger"; spanRef?: string | null } = {},
): void {
  const collector = RunCollector.current();
  if (!collector) return;
  collector.appendSignalHit(name, opts);
}
