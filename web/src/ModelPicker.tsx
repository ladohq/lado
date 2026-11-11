// The one picker of a model (docs/design/ui.md, Agent CLIs; New session): a field and a list that lies over the
// page, placed by the field so no card or dialog cuts it. Its rows, one order for every place:
// the CLI's settings, YOUR MODELS, BUILT-IN, `Other name…` only for a CLI with no full list.
// The list is what the core computes for the CLI (GET /api/providers/{name}/model-choices),
// read when the picker opens; its owner keeps the read (useModelChoices), so a warning from it
// can stand outside the picker. Choosing only reports a pick: its owner saves it. Plain rows,
// no virtual list: 321 rows draw at once and the search filters in place.
import {
  type KeyboardEvent,
  type RefObject,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { type CliDefault, type ConfiguredModelInfo, getModelChoices, type ModelChoices, unreachable } from "./api";
import { ChevronIcon, ServerIcon } from "./icons";
import { agentClisPath } from "./paths";
import { messageOf } from "./SessionControl";

const SEARCH_ABOVE = 10; // a list longer than this has a search field
const LIST_MAX = 420; // the list's height, at most
const OPEN_UP_BELOW = 240; // fewer pixels than this under the field: it may open upward
const GAP = 4; // between the field and the list
const EDGE = 8; // between the list and the window's edge
const PHONE = 600; // a narrower window keeps the list to 60% of its height
const LONG_SERVER = 24; // a server's name longer than this goes under the id in a row

export type Pick = { external: string } | { builtin: string } | null;

// A server as the last probe found it: silent, or its list (null: it gives none).
export type Health = { down: string } | { models: string[] | null };

export type ModelRead = {
  choices: ModelChoices | null;
  checked: string; // the model `choices.check` is of
  reading: boolean;
  problem: string | null; // the request failed: not a list that cannot be read
  read: (fresh: boolean, model: string) => void;
};

const fold = (text: string) => text.toLowerCase();
// A model named by its id shows the id once: as its name.
const idBeside = (name: string, model: string) => (fold(model) === fold(name) ? undefined : model);

export const sameModel = (a: CliDefault, b: CliDefault | null) =>
  b !== null && a.external === b.external && a.builtin === b.builtin;

// The reads of a CLI's list: the latest asked wins, so an older answer that comes late, or one
// after the page was left, changes nothing.
export function useModelChoices(cli: string): ModelRead {
  // Of the CLI it was read for: another CLI has no list until its own is read.
  const [held, setHeld] = useState<{ cli: string; choices: ModelChoices; checked: string } | null>(null);
  const [reading, setReading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const latest = useRef(0);
  useEffect(
    () => () => {
      latest.current++;
    },
    [],
  );
  const read = useCallback(
    (fresh: boolean, model: string) => {
      const asked = ++latest.current;
      setReading(true);
      setProblem(null);
      getModelChoices(cli, model, fresh).then(
        (found) => {
          if (asked !== latest.current) return;
          setHeld({ cli, choices: found, checked: model });
          setReading(false);
        },
        (error: unknown) => {
          if (asked !== latest.current) return;
          setProblem(unreachable(error) ? "LADO's server does not answer: the list was not read." : messageOf(error));
          setReading(false);
        },
      );
    },
    [cli],
  );
  const own = held?.cli === cli ? held : null;
  return { choices: own?.choices ?? null, checked: own?.checked ?? "", reading, problem, read };
}

// What a server's state says of `model` on it: a row's words, or nothing when all is well.
export function serverWords(health: Health | undefined, model: string): string | null {
  if (!health) return null;
  if ("down" in health) return "not answering";
  return health.models !== null && !health.models.includes(model) ? "not on the server" : null;
}

type Row = {
  key: string;
  // "read": a row that reads the list again and picks nothing; "stay": one that keeps the value
  pick: Pick | "other" | "read" | "stay";
  label: string; // what a screen reader says
  selected: boolean;
  title: string;
  id?: string; // a second line: a model's id, or what a row means
  mono?: boolean;
  server?: string;
  down?: boolean;
  mark?: string | null;
  isDefault?: boolean;
};

type Place = { top?: number; bottom?: number; left: number; width: number; maxHeight: number };

// Where the list goes for the field's box: under it, or over it when there is little room
// below and more above. The room is the visual viewport's, so a phone's keyboard counts.
function placeOf(field: HTMLElement): Place {
  const box = field.getBoundingClientRect();
  const view = window.visualViewport;
  const end = view ? view.offsetTop + view.height : window.innerHeight;
  const start = view?.offsetTop ?? 0;
  const below = end - box.bottom;
  const above = box.top - start;
  const up = below < OPEN_UP_BELOW && above > below;
  const room = (up ? above : below) - EDGE;
  const limit = window.innerWidth < PHONE ? Math.min(LIST_MAX, (end - start) * 0.6) : LIST_MAX;
  const maxHeight = Math.max(0, Math.min(limit, room));
  return up
    ? { bottom: window.innerHeight - box.top + GAP, left: box.left, width: box.width, maxHeight }
    : { top: box.bottom + GAP, left: box.left, width: box.width, maxHeight };
}

export function ModelPicker({
  cli,
  value,
  where,
  own,
  list,
  off,
  lost,
  health,
  fieldId,
  invalid = false,
  fieldMark = null,
  defaultModel = null,
  needsLogin = false,
  describedBy,
  fieldRef,
  onOpen,
  onPick,
  onOther,
}: {
  cli: { name: string; title: string };
  value: CliDefault | null;
  where: "settings" | "launch";
  own: ConfiguredModelInfo[]; // the CLI's configured models as the page has them, by name
  list: ModelRead;
  off: boolean; // shows its value and does not open
  lost: boolean; // the list lacks the built-in value
  health: Record<string, Health>; // by server, its name folded
  fieldId?: string; // a label of the owner's names the field (`where` launch)
  invalid?: boolean; // the value is refused
  fieldMark?: string | null; // why the value stands out, in the field
  defaultModel?: CliDefault | null; // marked `default` (`where` launch)
  // The CLI's own login is missing: its settings and built-in models are marked (`where` launch)
  needsLogin?: boolean;
  describedBy?: string;
  fieldRef?: RefObject<HTMLButtonElement | null>; // the owner hands the focus back to the field
  onOpen: () => void;
  onPick: (pick: Pick) => void;
  onOther: (typed: string) => void;
}) {
  const id = useId();
  const listId = `${id}-list`;
  const root = useRef<HTMLDivElement>(null);
  const ownField = useRef<HTMLButtonElement>(null);
  const field = fieldRef ?? ownField;
  const pop = useRef<HTMLDivElement>(null);
  const foot = useRef<HTMLDivElement>(null);
  const searchBox = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [place, setPlace] = useState<Place | null>(null);
  const [search, setSearch] = useState("");
  // The highlighted row, the one Enter picks, by its key: null is the first row.
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const typedAhead = useRef({ text: "", at: 0 });

  const { choices } = list;
  // The core's list once read; the page's entries only until then.
  const mine = choices && !list.reading ? choices.external : own;
  const built = [...new Set([...(choices?.aliases ?? []), ...(choices?.models ?? [])])];
  const total = mine.length + built.length;
  // Until the first read says how long the list is, and while it holds what was typed then.
  const searching = total > SEARCH_ABOVE || (choices === null && list.reading) || search !== "";
  const searchWords = list.reading ? "Search models" : `Search ${total} models`;
  const typed = fold(search.trim());
  const holds = (...texts: (string | null | undefined)[]) =>
    !typed || texts.some((text) => text != null && fold(text).includes(typed));

  // The built-in value the list lacks heads its group, saying why it is there.
  const extra =
    value?.builtin != null && !built.includes(value.builtin) && !fieldMark ? value.builtin : null;
  const extraMark = lost
    ? "no longer listed"
    : choices?.models === null && !choices.read_again
      ? "other name"
      : null;

  const loginMark = needsLogin ? "needs login" : null;
  const settingsRow: Row = {
    key: "settings",
    pick: null,
    label: `${cli.title}'s settings`,
    selected: value === null,
    title: `${cli.title}'s settings`,
    id: "no model set: the agent CLI chooses",
    mark: loginMark,
  };
  // A value that stands out (a model no longer saved) is of no group: above them, kept by a pick.
  const standing: Row | null =
    fieldMark && value !== null && holds(value.name)
      ? {
          key: "standing",
          pick: "stay",
          label: value.name,
          selected: true,
          title: value.name,
          mark: fieldMark,
        }
      : null;
  const yours: Row[] = mine
    .filter((m) => holds(m.name, m.model, m.server))
    .map((m) => {
      const state = health[fold(m.server)];
      return {
        key: `external:${m.id}`,
        pick: { external: m.id },
        label: `${m.name}, ${m.model}, on the model server ${m.server}`,
        selected: value?.external === m.id,
        title: m.name,
        id: idBeside(m.name, m.model),
        server: m.server,
        down: state !== undefined && "down" in state,
        mark: serverWords(state, m.model),
        isDefault: defaultModel?.external === m.id,
      };
    });
  const builtin = (model: string, mark: string | null): Row => ({
    key: `builtin:${model}`,
    pick: { builtin: model },
    label: model,
    selected: value?.builtin === model,
    title: model,
    mono: true,
    mark,
    isDefault: defaultModel?.builtin === model,
  });
  const builtins: Row[] = [
    ...(extra !== null && holds(extra) ? [builtin(extra, extraMark ?? loginMark)] : []),
    ...built.filter((model) => holds(model)).map((model) => builtin(model, loginMark)),
  ];
  const otherRow: Row | null = choices?.other_name
    ? {
        key: "other",
        pick: "other",
        label: "Other name…",
        selected: false,
        title: "Other name…",
        id: "a name LADO cannot check",
      }
    : null;
  const noList = choices?.models === null && choices.aliases.length === 0;
  // A row, not a button: Tab closes the list, so only a row is in the keyboard's reach.
  const readRow: Row | null =
    !list.reading && (list.problem !== null || (noList && choices?.read_again))
      ? { key: "read", pick: "read", label: "Read again", selected: false, title: "Read again" }
      : null;
  const rows = [
    ...(typed ? [] : [settingsRow]),
    ...(typed || !readRow ? [] : [readRow]),
    ...(standing ? [standing] : []),
    ...yours,
    ...builtins,
    ...(otherRow ? [otherRow] : []),
  ];
  const shownModels = yours.length + builtins.length;
  // Its place follows from the rows of this render, so a row that comes or goes above it moves
  // it to no other row; while its row is gone it stands on the selected one, and the key, kept,
  // takes it back when the row comes again.
  const keyAt = activeKey === null ? 0 : rows.findIndex((row) => row.key === activeKey);
  const active = keyAt >= 0 ? keyAt : Math.max(0, rows.findIndex((row) => row.selected));
  const setActive = (at: number) => setActiveKey(rows[at]?.key ?? null);

  const close = useCallback(
    (refocus: boolean) => {
      setOpen(false);
      setPlace(null);
      setSearch("");
      if (refocus) field.current?.focus({ preventScroll: true });
    },
    [field],
  );

  const opening = () => {
    if (off) return;
    onOpen();
    list.read(true, value?.builtin ?? "");
    setOpen(true);
  };

  // On the selected row once the list is open, and again when a list is read anew; rows that
  // come or go without one (Read again after a failed request) leave it on its row.
  useLayoutEffect(() => {
    if (!open) return;
    setActiveKey(rows.find((row) => row.selected)?.key ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- when it opens and at each read
  }, [open, choices]);

  useLayoutEffect(() => {
    if (!open || !field.current) return;
    const target = field.current;
    const again = () => setPlace(placeOf(target));
    again();
    const view = window.visualViewport;
    window.addEventListener("resize", again);
    window.addEventListener("scroll", again, true);
    view?.addEventListener("resize", again);
    view?.addEventListener("scroll", again);
    return () => {
      window.removeEventListener("resize", again);
      window.removeEventListener("scroll", again, true);
      view?.removeEventListener("resize", again);
      view?.removeEventListener("scroll", again);
    };
  }, [open, field]);

  // A press outside closes it; so does a scroll the human starts outside the list, never one
  // of the page's own, which only moves it.
  useEffect(() => {
    if (!open) return;
    const outside = (event: Event) => !root.current?.contains(event.target as Node);
    // What the press lands on keeps the focus; a press on nothing leaves it on the field.
    const press = (event: Event) => {
      if (!outside(event)) return;
      close(false);
      setTimeout(() => {
        if (document.activeElement === document.body) field.current?.focus({ preventScroll: true });
      });
    };
    const scroll = (event: Event) => !pop.current?.contains(event.target as Node) && close(true);
    document.addEventListener("pointerdown", press);
    document.addEventListener("wheel", scroll, { passive: true });
    document.addEventListener("touchmove", scroll, { passive: true });
    return () => {
      document.removeEventListener("pointerdown", press);
      document.removeEventListener("wheel", scroll);
      document.removeEventListener("touchmove", scroll);
    };
  }, [open, close, field]);

  // A list read short takes the search away: the focus goes back to the field.
  const hadSearch = useRef(false);
  useEffect(() => {
    if (open && searching) searchBox.current?.focus();
    else if (open && hadSearch.current) field.current?.focus({ preventScroll: true });
    hadSearch.current = open && searching;
  }, [open, searching, field]);

  useEffect(() => {
    if (open) document.getElementById(`${id}-${active}`)?.scrollIntoView?.({ block: "nearest" });
  }, [open, active, id]);

  // A read may take away what had the focus (↻, when reading again cannot help): with the focus
  // on nothing the keys would miss the list, and Esc close the window around it.
  useEffect(() => {
    if (open && document.activeElement === document.body) {
      (searchBox.current ?? field.current)?.focus({ preventScroll: true });
    }
  }, [open, choices, field]);

  const choose = (row: Row | undefined) => {
    if (!row) return;
    if (row.pick === "read") return list.read(true, value?.builtin ?? "");
    const text = search.trim();
    close(row.pick !== "other");
    if (row.pick === "other") onOther(text);
    else if (row.pick !== "stay") onPick(row.pick);
  };

  const footControls = () => [...(foot.current?.querySelectorAll<HTMLElement>("a, button") ?? [])];

  // Tab from the rows goes on into the foot; true when it did.
  const intoFoot = (event: KeyboardEvent): boolean => {
    const [first] = footControls();
    if (event.shiftKey || !first) return false;
    event.preventDefault();
    first.focus();
    return true;
  };

  const onFootKey = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close(true);
    } else if (event.key === "Tab") {
      const controls = footControls();
      const at = controls.indexOf(event.target as HTMLElement);
      if (event.shiftKey && at === 0) {
        event.preventDefault();
        (searchBox.current ?? field.current)?.focus();
      } else if (!event.shiftKey && at === controls.length - 1) {
        close(true); // the list goes: Tab goes on from the field
      }
    }
  };

  const moved = (event: KeyboardEvent): boolean => {
    const last = rows.length - 1;
    const to: Record<string, number> = {
      ArrowDown: Math.min(active + 1, last),
      ArrowUp: Math.max(active - 1, 0),
      Home: 0,
      End: last,
    };
    if (!(event.key in to)) return false;
    event.preventDefault();
    setActive(to[event.key]);
    return true;
  };

  const onFieldKey = (event: KeyboardEvent) => {
    if (!open) {
      if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        opening();
      }
      return;
    }
    if (moved(event)) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      choose(rows[active]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close(true);
    } else if (event.key === "Tab") {
      if (!intoFoot(event)) close(false);
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const now = Date.now();
      const text = (now - typedAhead.current.at < 700 ? typedAhead.current.text : "") + fold(event.key);
      typedAhead.current = { text, at: now };
      const found = rows.findIndex((row) => fold(row.title).startsWith(text));
      if (found >= 0) setActive(found);
    }
  };

  const onSearchKey = (event: KeyboardEvent) => {
    if (moved(event)) return;
    if (event.key === "Tab" && event.shiftKey) {
      event.preventDefault(); // to the field, not on past it
      close(true);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      choose(rows[active]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      if (search) {
        setSearch("");
        setActiveKey(null);
      } else close(true);
    } else if (event.key === "Tab") {
      if (!intoFoot(event)) close(true); // the search goes with the list: Tab goes on from the field
    }
  };

  const option = (row: Row) => {
    const at = rows.indexOf(row);
    return (
      <div
        key={row.key}
        id={`${id}-${at}`}
        role="option"
        aria-label={row.label}
        aria-selected={row.selected}
        className={`mp-opt${at === active ? " mp-active" : ""}${row.selected ? " mp-selected" : ""}${
          row.pick === "other" ? " mp-other" : row.pick === "read" ? " mp-read" : ""
        }${(row.server?.length ?? 0) > LONG_SERVER ? " mp-long" : ""}`}
        onPointerMove={() => setActive(at)}
        onClick={() => choose(row)}
      >
        <span className="mp-check" aria-hidden="true">
          {row.selected ? "✓" : ""}
        </span>
        <span className="mp-names">
          <span className={row.mono ? "mp-title mono" : "mp-title"}>{row.title}</span>
          {row.id && <span className={row.server ? "mp-sub mono" : "mp-sub"}>{row.id}</span>}
        </span>
        {row.isDefault && <span className="mc-default">default</span>}
        {row.mark && <span className="mx-gone">{row.mark}</span>}
        {row.server && <Server name={row.server} down={row.down ?? false} />}
      </div>
    );
  };

  const yoursGroup = yours.length > 0 && (
    <div role="group" aria-label="YOUR MODELS">
      <div className="mp-group" aria-hidden="true">
        YOUR MODELS
      </div>
      {choices?.whole_process && (
        <p className="mp-say">{`On ${cli.title} a server's model takes the whole process: the agent runs only on that server.`}</p>
      )}
      {yours.map(option)}
    </div>
  );
  const builtTitle = choices?.models === null && built.length > 0 ? "BUILT-IN · aliases" : "BUILT-IN";
  const builtGroup = builtins.length > 0 && (
    <div role="group" aria-label={builtTitle}>
      <div className="mp-group" aria-hidden="true">
        {builtTitle}
      </div>
      {builtins.map(option)}
    </div>
  );

  const count = [
    choices?.models != null && `${choices.models.length} built-in`,
    choices?.models === null && built.length > 0 && `${built.length} aliases`,
    `${mine.length} of yours`,
  ]
    .filter(Boolean)
    .join(" · ");

  const state = value?.server ? health[fold(value.server)] : undefined;
  const launching = where === "launch";
  const valueIsDefault = launching && value !== null && sameModel(value, defaultModel);
  return (
    <div className="mp-box" ref={root} data-where={where}>
      <button
        ref={field}
        id={fieldId}
        type="button"
        className="model-pick"
        role="combobox"
        aria-label={launching ? undefined : `Default model of ${cli.title}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open && !searching ? `${id}-${active}` : undefined}
        aria-describedby={describedBy}
        aria-invalid={launching ? invalid : undefined}
        disabled={off}
        title={value ? [value.name, value.model, value.server].filter(Boolean).join(" · ") : undefined}
        onClick={() => (open ? close(true) : opening())}
        onKeyDown={onFieldKey}
      >
        <span className="mp-value">
          {value === null && <span className="muted">{`${cli.title}'s settings`}</span>}
          {value?.builtin != null && (
            <span className={fieldMark ? "mp-title" : "mp-title mono"}>{value.builtin}</span>
          )}
          {value?.external != null && (
            <>
              <span className="mp-title">{value.name}</span>
              {idBeside(value.name, value.model) && <span className="mp-id mono">{value.model}</span>}
            </>
          )}
        </span>
        {valueIsDefault && <span className="mc-default">default</span>}
        {lost && <span className="mx-gone">⚠ no longer listed</span>}
        {fieldMark && <span className="mx-gone">{fieldMark}</span>}
        {value?.server && <Server name={value.server} down={state !== undefined && "down" in state} />}
        <span className="mp-arrow" aria-hidden="true">
          <ChevronIcon />
        </span>
      </button>
      {open && (
        <div
          ref={pop}
          className="mp-pop"
          // A press in the list takes no focus: it stays where the keyboard works the list.
          onMouseDown={(event) => {
            if (!(event.target instanceof HTMLInputElement)) event.preventDefault();
          }}
          style={{
            position: "fixed",
            top: place?.top,
            bottom: place?.bottom,
            left: place?.left,
            width: place?.width,
            maxHeight: place?.maxHeight,
          }}
        >
          {searching && (
            <input
              ref={searchBox}
              className="mx-search mp-search"
              type="search"
              role="combobox"
              aria-label={searchWords}
              aria-expanded="true"
              aria-controls={listId}
              aria-activedescendant={`${id}-${active}`}
              placeholder={searchWords}
              autoComplete="off"
              spellCheck={false}
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setActiveKey(null); // a search starts at its first row
              }}
              onKeyDown={onSearchKey}
            />
          )}
          {(noList || list.problem) && !list.reading && (
            <div className="mp-why">
              <span>{`⚠ ${list.problem ?? choices?.why}`}</span>
            </div>
          )}
          <div className="mp-list" id={listId} role="listbox" aria-label={`Models of ${cli.title}`}>
            {!typed && option(settingsRow)}
            {!typed && readRow && option(readRow)}
            {standing && option(standing)}
            {yoursGroup}
            {builtGroup}
            {typed && shownModels === 0 && <p className="mp-none">{`No model matches “${search}”.`}</p>}
            {otherRow && option(otherRow)}
          </div>
          {list.reading && (
            <p className="mp-reading" role="status">
              <span className="mx-spin" aria-hidden="true" /> reading the models…
            </p>
          )}
          {(!list.reading || choices !== null) && (
            <div className="mp-foot" ref={foot} onKeyDown={onFootKey}>
              {launching && !typed ? (
                <span>
                  The default comes from{" "}
                  <a href={agentClisPath()} target="_blank" rel="noopener">
                    Settings → Agent CLIs
                  </a>
                  .
                </span>
              ) : (
                <span role="status">{typed ? `${shownModels} of ${total}` : count}</span>
              )}
              {choices?.read_again && (
                <button
                  type="button"
                  className="mx-icon mx-refresh"
                  aria-label="Read the models again"
                  title="Read the models again"
                  onClick={() => list.read(true, value?.builtin ?? "")}
                >
                  ↻
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// A model server's mark: its name, with a sign and not colour alone when it does not answer.
function Server({ name, down }: { name: string; down: boolean }) {
  return (
    <span className={`srv${down ? " down" : ""}`} title={name}>
      <ServerIcon />
      {down && <span aria-hidden="true">⚠</span>}
      <span className="srv-t">{name}</span>
    </span>
  );
}
