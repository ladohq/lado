// The human's model settings (GET /api/model-settings, which asks no server), read by the page
// that shows them when it opens and after each change of its own: Settings → Agent CLIs (each
// CLI's default) and Model servers (the servers and Your models). No state outlives the page.
import { useCallback, useEffect, useRef, useState } from "react";

import { getModelSettings, type ModelSettings as Entries, refusalOf } from "./api";

export type ModelSettingsState = {
  entries: Entries | null;
  problem: string | null;
  // Takes `given` (a change's answer), else reads them; the latest call's answer wins.
  reload: (given?: Entries) => Promise<void>;
};

export function useModelSettings(): ModelSettingsState {
  const [entries, setEntries] = useState<Entries | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const latest = useRef(0);
  const reload = useCallback(async (given?: Entries) => {
    const asked = ++latest.current;
    try {
      const found = given ?? (await getModelSettings());
      if (asked !== latest.current) return;
      // A server of another version may answer otherwise (the banner says it is one).
      if (!Array.isArray(found?.models) || !Array.isArray(found?.servers) || !Array.isArray(found?.defaults))
        throw new Error("the server gave no models: reload the page");
      setEntries(found);
      setProblem(null);
    } catch (error) {
      if (asked === latest.current) setProblem(refusalOf(error).message);
    }
  }, []);
  useEffect(() => {
    void reload();
    return () => {
      latest.current++; // no answer counts once the page left
    };
  }, [reload]);
  return { entries, problem, reload };
}
