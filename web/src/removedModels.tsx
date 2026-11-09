// A model removed on Settings → Model servers (docs/design/ui.md, Model servers), by × in Your
// models or by its tick under a server's model: one state, one Undo and one UNDO_MS for both.
// Nothing asks first; the line shows only where the human acted (`at`), offers Undo for UNDO_MS,
// then stays without it until the human's next change on the page. Undo saves the model again
// under its name and sets its CLI's default again when it was one.
import { useCallback, useEffect, useRef, useState } from "react";

import { addModel, type ConfiguredModelInfo, type ModelSettings, refusalOf, setModelDefault } from "./api";

// How long a removed model offers Undo; its line then stays.
export const UNDO_MS = 10000;

// `at`: the key of the tick it was unticked by, null for × in Your models. `problem`: why Undo
// was refused, or (`back`) why the model came back without its default. `expired`: no more Undo.
export type Removed = {
  model: ConfiguredModelInfo;
  wasDefault: boolean;
  at: string | null;
  problem: string | null;
  busy: boolean;
  expired: boolean;
  back: boolean;
};

export type RemovedModels = {
  list: Removed[];
  add: (model: ConfiguredModelInfo, wasDefault: boolean, at: string | null) => void;
  // Resolves true once the model is back (its default perhaps not: the line says why).
  undo: (gone: Removed) => Promise<boolean>;
  expire: (gone: Removed) => void;
  forget: (which: (gone: Removed) => boolean) => void;
  touch: () => void; // the human's next change: the lines without Undo go
};

const fold = (text: string) => text.toLowerCase();

export function useRemovedModels(reload: (given?: ModelSettings) => Promise<void>): RemovedModels {
  const [removed, setRemoved] = useState<Record<string, Removed>>({}); // by folded name
  const set = useCallback(
    (name: string, gone: Removed | null) =>
      setRemoved((now) => {
        const next = { ...now };
        if (gone) next[fold(name)] = gone;
        else delete next[fold(name)];
        return next;
      }),
    [],
  );
  const forget = useCallback(
    (which: (gone: Removed) => boolean) =>
      setRemoved((now) =>
        Object.values(now).some(which) ? Object.fromEntries(Object.entries(now).filter(([, g]) => !which(g))) : now,
      ),
    [],
  );
  const touch = useCallback(() => forget((gone) => gone.expired), [forget]);
  const add = useCallback(
    (model: ConfiguredModelInfo, wasDefault: boolean, at: string | null) =>
      set(model.name, { model, wasDefault, at, problem: null, busy: false, expired: false, back: false }),
    [set],
  );
  const expire = useCallback((gone: Removed) => set(gone.model.name, { ...gone, expired: true }), [set]);
  const undo = async (gone: Removed) => {
    const { model } = gone;
    set(model.name, { ...gone, busy: true, problem: null });
    let id: string;
    try {
      id = (await addModel({ name: model.name, cli: model.cli, model: model.model, server: model.server })).model.id;
    } catch (error) {
      set(model.name, { ...gone, busy: false, problem: refusalOf(error).message });
      void reload();
      return false;
    }
    // The line goes only once the reload has brought the model back: nothing moves.
    if (gone.wasDefault) {
      try {
        await reload((await setModelDefault(model.cli, { external: id })).settings);
      } catch (error) {
        // The model is back; only its default is not: the line says why until the next change.
        await reload();
        set(model.name, { ...gone, busy: false, expired: true, back: true, problem: refusalOf(error).message });
        return true;
      }
    } else await reload();
    set(model.name, null);
    return true;
  };
  return { list: Object.values(removed), add, undo, expire, forget, touch };
}

// The line of a removed model: `Removed <name>.` (and that its CLI is back on its settings), why
// Undo was refused, and Undo until it expires. In Your models a row of its table (`row`), where ×
// hands the focus to Undo; under a tick a plain line, the focus staying on the tick.
export function UndoLine({
  gone,
  className,
  row = false,
  onUndo,
  onExpired,
  onLeft,
}: {
  gone: Removed;
  className: string;
  row?: boolean;
  onUndo: (gone: Removed) => void;
  onExpired: (gone: Removed) => void;
  onLeft: () => void; // Undo went with the focus on it
}) {
  const { model, wasDefault, problem, busy, expired, back } = gone;
  const undo = useRef<HTMLButtonElement>(null);
  const left = useRef(onLeft);
  left.current = onLeft;
  // Undo goes after UNDO_MS, kept while it runs or was refused (to say why); the line stays.
  // The callbacks are the latest ones: the page renders again under it (a read of the CLIs'
  // rows each second), which must not start the time over.
  const latest = useRef(gone);
  latest.current = gone;
  const expire = useRef(onExpired);
  expire.current = onExpired;
  useEffect(() => {
    if (problem || busy || expired) return;
    const timer = setTimeout(() => {
      if (document.activeElement === undo.current) left.current();
      expire.current(latest.current);
    }, UNDO_MS);
    return () => clearTimeout(timer);
  }, [problem, busy, expired]);
  return (
    <div className={className} role={row ? "row" : undefined}>
      <span role={row ? "cell" : undefined}>
        {!back && (
          <span role="status">
            Removed <b>{model.name}</b>.{wasDefault && ` ${model.cli_title} is back on its settings.`}
          </span>
        )}
        {problem && <span className="field-note bad">{problem}</span>}
      </span>
      {!expired && (
        // Off while it runs by aria only: a button truly disabled would drop the focus, and a
        // refusal leaves it here.
        <button
          ref={undo}
          type="button"
          className="link-button"
          autoFocus={row}
          aria-disabled={busy ? true : undefined}
          onClick={() => !busy && onUndo(gone)}
        >
          Undo
        </button>
      )}
    </div>
  );
}
