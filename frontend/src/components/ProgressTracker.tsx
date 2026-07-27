import { useEffect } from "react";
import { useRedactionStore } from "../stores/redactionStore";

const STEP_MS = 80;

/**
 * Headless component. Drives the progressive redaction animation by bumping
 * visibleCount once per STEP_MS until all entities are revealed. Mounted by
 * App and renders nothing.
 */
export function ProgressTracker() {
  const status = useRedactionStore((s) => s.status);
  const total = useRedactionStore((s) => s.entities.length);
  const visible = useRedactionStore((s) => s.visibleCount);
  const bump = useRedactionStore((s) => s.bumpVisible);
  const finish = useRedactionStore((s) => s.finishAnimation);

  useEffect(() => {
    if (status !== "animating") return;
    if (visible >= total) {
      finish();
      return;
    }
    const t = window.setTimeout(bump, STEP_MS);
    return () => window.clearTimeout(t);
  }, [status, visible, total, bump, finish]);

  return null;
}
