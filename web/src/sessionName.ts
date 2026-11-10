// The session's name the New session window offers (docs/design/ui.md, Launch and session
// control): the task's tracker key until the human types one, else the place's name. The rule
// lives here, in the window, which has the task as it is typed, the place's default name and
// the sessions; the server stays the authority on a name (runtime.slug, a 409 when taken).

// A tracker key anywhere in the task: 2 or more capital Latin letters, "-", digits, a word of
// its own (no letter or digit right before or after). "UTF-8" fits too: the name shows before
// the start, and the human changes it.
const KEY = /(?<![A-Za-z0-9])([A-Z]{2,}-[0-9]+)(?![A-Za-z0-9])/;
const MIN_TYPED = 2; // a typed name's plain form shorter than this is no name

// The core's runtime.slug: small letters, each run of anything but a-z, 0-9, "_" and "-" one
// "-", none at the ends. Empty when nothing is left (the core then says "lado"). Accents are
// not folded, as the core does not fold them (sessionSlug.cases.json holds the two to one rule).
export function slug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// The base of the automatic name: the task's first tracker key, in small letters; else the
// place's name (null while there is none). The task's other words never make a name.
export function autoBase(task: string, placeBase: string | null): string | null {
  const key = KEY.exec(task);
  return key ? key[1].toLowerCase() : placeBase;
}

// `base` when no session has it, else the first of `base-2`, `base-3`, … that none has, as the
// core's runtime.free_name.
export function freeName(base: string, taken: ReadonlySet<string>): string {
  let name = base;
  for (let n = 2; taken.has(name); n += 1) name = `${base}-${n}`;
  return name;
}

// The free name after the taken `id`: a numbered name of a taken series (`webapp-2`, with
// `webapp` taken) goes on with its series (`webapp-3`); a number that is part of the name
// (`lad-263`) stays in it (`lad-263-2`).
export function nextFree(id: string, taken: ReadonlySet<string>): string {
  const all = new Set([...taken, id]);
  const numbered = /^(.+)-\d+$/.exec(id);
  return freeName(numbered && all.has(numbered[1]) ? numbered[1] : id, all);
}

export type NameMode = "auto" | "custom";

export type SessionName = {
  id: string | null; // the name the start sends; null: none yet
  title: string | null; // the typed text when it differs from id
  base: string | null; // the name before its number
  numbered: boolean; // an automatic name taken, so numbered
  taken: boolean; // a typed name a session has
};

// The session's name: in "auto" the automatic one, numbered when taken; in "custom" the plain
// form of `typed` (its text the title), kept as it is when taken; a typed text without a plain
// form of two characters is the title of the automatic name.
export function sessionName({
  mode,
  typed,
  task,
  placeBase,
  taken,
}: {
  mode: NameMode;
  typed: string;
  task: string;
  placeBase: string | null;
  taken: ReadonlySet<string>;
}): SessionName {
  const plain = mode === "custom" ? slug(typed) : "";
  if (plain.length >= MIN_TYPED) {
    const title = typed.trim();
    return { id: plain, title: title === plain ? null : title, base: plain, numbered: false, taken: taken.has(plain) };
  }
  const base = autoBase(task, placeBase);
  const id = base === null ? null : freeName(base, taken);
  const title = mode === "custom" && typed.trim() !== "" ? typed.trim() : null;
  return { id, title, base, numbered: id !== base, taken: false };
}
