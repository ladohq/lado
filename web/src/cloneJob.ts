// The client of a clone job of the server (docs/design/ui.md, Launch: Clone from URL), one
// for every screen that clones: the New session window's Clone and start and the project
// page's Add repository. What a screen does after the clone stays the screen's.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { ApiError, cancelClone, cancelCloneOnLeave, getClone, startClone, type CloneJob, type CloneStart } from "./api";

// How often a screen asks for its clone job; the server cancels one no one asks about.
export const CLONE_POLL = 500;

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// How a clone job ended for the screen that ran it:
// - done: the clone is there; `late` when Cancel clone was pressed but came too late;
// - cancelled, failed (its `error`): no clone;
// - away: the server forgot a job that ended while no one asked (clone.KEPT), and the
//   clone is there (the screen's own `isThere`); gone: it is not, `error` the server's 404;
// - left: the screen went away while it ran; it does nothing more.
export type CloneEnd =
  | { done: CloneJob; late: boolean }
  | { ended: "cancelled" | "failed" | "away" | "left"; job: CloneJob }
  | { ended: "gone"; job: CloneJob; error: ApiError };

export type CloneJobClient = {
  job: CloneJob | null; // the running job, for its progress; null when none runs
  // Start the job and follow it to its end; a refused start throws the server's ApiError.
  run: (start: CloneStart, isThere: (job: CloneJob) => Promise<boolean>) => Promise<CloneEnd>;
  cancel: () => void; // Cancel clone: the server stops git and removes its folder
};

export function useCloneJob(): CloneJobClient {
  const [job, setJob] = useState<CloneJob | null>(null);
  const alive = useRef(true);
  const current = useRef<CloneJob | null>(null);
  const cancelPressed = useRef(false);

  useEffect(() => {
    alive.current = true; // again after StrictMode's trial unmount
    return () => {
      alive.current = false;
    };
  }, []);

  // A page that goes away (tab closed or reloaded) cancels its running clone at once; the
  // server's clone.ABANDONED is only the fallback for a page that could not say so. A
  // layout effect: the listener is there in the very commit that shows the clone running
  // and gone in the one that shows its end; a passive effect runs a task later, when a
  // page that went away in between has cancelled nothing.
  const runningId = job?.state === "running" ? job.id : null;
  useLayoutEffect(() => {
    if (runningId === null) return;
    const leave = () => cancelCloneOnLeave(runningId);
    window.addEventListener("pagehide", leave);
    return () => window.removeEventListener("pagehide", leave);
  }, [runningId]);

  const show = (shown: CloneJob | null) => {
    current.current = shown;
    setJob(shown);
  };

  const run = useCallback(async (start: CloneStart, isThere: (job: CloneJob) => Promise<boolean>): Promise<CloneEnd> => {
    cancelPressed.current = false;
    let running = await startClone(start);
    show(running);
    while (running.state === "running") {
      await pause(CLONE_POLL);
      if (!alive.current) return { ended: "left", job: running };
      try {
        running = await getClone(running.id);
      } catch (error) {
        // A job the server no longer knows (it restarted, or dropped one that ended while
        // no one asked) has ended; any other failure is asked again, as the clone goes on
        // and only Cancel clone ends it.
        if (error instanceof ApiError && error.status === 404) {
          const there = await isThere(running).catch(() => false);
          show(null);
          return there ? { ended: "away", job: running } : { ended: "gone", job: running, error };
        }
        continue;
      }
      show(running);
    }
    show(null);
    if (running.state === "done") return { done: running, late: cancelPressed.current };
    return { ended: running.state === "failed" ? "failed" : "cancelled", job: running };
  }, []);

  const cancel = useCallback(() => {
    const running = current.current;
    if (running === null) return;
    cancelPressed.current = true;
    void cancelClone(running.id).catch(() => {});
  }, []);

  return { job, run, cancel };
}
