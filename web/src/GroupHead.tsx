// A list group's heading, one for every list (the session list, a tab's ListPage): a band
// in the group's tone, its name in small capitals and how many rows it has now. With `fold`
// the whole band is a button that opens and folds the group (the chevron shows which); the
// element `controls` names stays in the page either way. The tone sets `--g` and
// `--g-ground` (styles.css), which the group's rows take too.
import { ChevronIcon } from "./icons";

// human: what waits for the human; done: what works now; neutral: the rest.
export type Tone = "human" | "done" | "neutral";

// `disabled`: the list shows the group open whatever is chosen (a search), so the button is off.
export type Fold = { open: boolean; controls: string; onToggle: () => void; disabled?: boolean };

export function GroupHead({
  nameId,
  name,
  count,
  tone = "neutral",
  fold,
}: {
  nameId: string; // the name's id, for the group's aria-labelledby
  name: string;
  count: number;
  tone?: Tone;
  fold?: Fold;
}) {
  // The space between keeps the name and the count apart in what a screen reader says.
  const label = (
    <>
      <span id={nameId} className="group-name">
        {name}
      </span>{" "}
      <span className="group-count">{count}</span>
    </>
  );
  return (
    <h3 className={`group-head tone-${tone}`}>
      {fold ? (
        <button
          type="button"
          className="group-fold"
          aria-expanded={fold.open}
          aria-controls={fold.controls}
          onClick={fold.onToggle}
          disabled={fold.disabled}
        >
          <ChevronIcon />
          {label}
        </button>
      ) : (
        label
      )}
    </h3>
  );
}
