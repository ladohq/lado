// The session's name the New session window offers (docs/design/ui.md, Launch and session
// control): made from the task until the human types one, else from the place. The rule
// lives here, in the window, which has the task as it is typed, the place's default name and
// the sessions; the server stays the authority on a name (runtime.slug, a 409 when taken).

// Small words a name does without.
const FILLER = new Set(
  "a an the to of for in on at by with and or please pls we i you it is be this that our my".split(" "),
);
// A tracker key that starts a line ("LAD-263: …", "[LAD-263] …", "LAD-263"), followed by an
// end of its own: a colon, a bracket, a dash or the line's end. "HTTP-2 support" and "PEP-8
// style" go on with a word, so they are words, not keys.
const KEY = /^[^A-Za-z0-9]*([A-Z][A-Z0-9]{1,9}-[0-9]{1,7})(?![A-Za-z0-9])(?=\s*(?:[:\])—–]|-\s|$))/;
const MAX_WORDS = 3;
const MAX_LENGTH = 32;
const MIN_LENGTH = 3; // shorter words say less than the place's name
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

// The base of the automatic name: the key that starts the task's first line with text, in
// small letters; else up to three of that line's words without filler, joined by "-", at most
// 32 characters and at least 3; else the place's name (null while there is none).
export function autoBase(task: string, placeBase: string | null): string | null {
  const line = task.split("\n").find((l) => l.trim() !== "")?.trim() ?? "";
  const key = KEY.exec(line);
  if (key) return key[1].toLowerCase();
  const words = line
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((w) => w !== "" && !FILLER.has(w));
  let joined = "";
  for (const word of words.slice(0, MAX_WORDS)) {
    if (joined === "") joined = word.slice(0, MAX_LENGTH);
    else if (joined.length + 1 + word.length <= MAX_LENGTH) joined = `${joined}-${word}`;
    else break;
  }
  return joined.length >= MIN_LENGTH ? joined : placeBase;
}

// `base` when no session has it, else the first of `base-2`, `base-3`, … that none has, as the
// core's runtime.free_name.
export function freeName(base: string, taken: ReadonlySet<string>): string {
  let name = base;
  for (let n = 2; taken.has(name); n += 1) name = `${base}-${n}`;
  return name;
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
