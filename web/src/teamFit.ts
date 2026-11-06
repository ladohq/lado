// The rules of the team in a session's head, with no browser (docs/design/ui.md, Session
// head): how a name is shortened (fitLabel), an agent's mark on its avatar (agentMarks), and
// the order in which the levels are tried (teamSteps, chooseLevel, stepFits). The trial itself,
// which measures, is Team.tsx's.

// The fewest letters of a stem a shortened name keeps.
const LEAST = 4;

// What ends a name: a number, or (names cut alike) its last word; with its separator.
const NUMBER = /^(.*?)([-_.]\d+)$/;
const WORD = /^(.*?)([-_.][^-_.]+)$/;

function split(name: string, tail: RegExp): [string, string] {
  const found = name.match(tail);
  return found ? [found[1]!, found[2]!] : [name, ""];
}

function cut(name: string, k: number, tail: RegExp): string {
  const [stem, end] = split(name, tail);
  return stem.length <= k ? name : `${stem.slice(0, k)}…${end}`;
}

// `found` with what repeats told apart: the later ones take `mark(2)`, `mark(3)`.
function apart(found: string[], mark: (count: number) => string): string[] {
  const seen = new Map<string, number>();
  return found.map((one) => {
    const count = (seen.get(one) ?? 0) + 1;
    seen.set(one, count);
    return count > 1 ? one + mark(count) : one;
  });
}

// `name` cut to `k` letters of its stem, told from the other `names` of the team.
export function fitLabel(name: string, k: number, names: string[]): string {
  const first = names.map((one) => cut(one, k, NUMBER));
  const second = names.map((one, i) =>
    first[i] !== one && first.filter((label) => label === first[i]).length > 1 ? cut(one, k, WORD) : first[i]!,
  );
  return apart(second, (count) => `·${count}`)[names.indexOf(name)]!;
}

// Each agent's mark, by its name, told from the whole team. Colour carries no difference.
export function agentMarks(names: string[]): Map<string, string> {
  const parts = names.map((name) => {
    const [stem, tail] = split(name, NUMBER);
    const number = tail.slice(1);
    return {
      name,
      flat: stem.replace(/[-_.]/g, ""),
      number: number.length >= 3 ? number.slice(-3) : number,
    };
  });
  const letter = (flat: string) => (Array.from(flat)[0] ?? "?").toUpperCase();
  const base = ({ flat, number }: (typeof parts)[number]) => (number.length === 3 ? number : letter(flat) + number);
  const groups = new Map<string, typeof parts>();
  for (const one of parts) groups.set(base(one), [...(groups.get(base(one)) ?? []), one]);
  const marks = new Map<string, string>();
  for (const [mark, group] of groups) {
    if (group.length === 1) {
      marks.set(group[0]!.name, mark);
      continue;
    }
    let at = 0;
    while (group.every(({ flat }) => flat[at] !== undefined && flat[at] === group[0]!.flat[at])) at++;
    for (const { name, flat, number } of group) {
      marks.set(name, letter(flat) + (at > 0 ? (flat[at]?.toUpperCase() ?? "") : "") + number);
    }
  }
  const told = apart(
    names.map((name) => marks.get(name)!),
    String,
  );
  return new Map(names.map((name, i) => [name, told[i]!]));
}

// A candidate of the trial: 0 whole names, 1 names of `k` letters, 2 avatars, 3 the first
// `visible` avatars.
export type TeamStep = { level: 0 } | { level: 1; k: number } | { level: 2 } | { level: 3; visible: number };

// Every candidate for a team of `names`, widest first.
export function teamSteps(names: string[]): TeamStep[] {
  const longest = Math.max(LEAST, ...names.map((name) => split(name, NUMBER)[0].length));
  const steps: TeamStep[] = [{ level: 0 }];
  for (let k = longest; k >= LEAST; k--) steps.push({ level: 1, k });
  steps.push({ level: 2 });
  for (let visible = names.length - 1; visible >= 0; visible--) steps.push({ level: 3, visible });
  return steps;
}

// The first of `steps` that fits, or the last.
export function chooseLevel(steps: TeamStep[], fits: (step: TeamStep) => boolean): TeamStep {
  return steps.find(fits) ?? steps[steps.length - 1]!;
}

// Whether a step fits, given that its row fits and that the title keeps its limit: the limit
// counts at names only, as agents behind `+N` cost more than a few letters of a title.
export function stepFits(step: TeamStep, row: boolean, title: boolean): boolean {
  return row && (step.level >= 2 || title);
}
