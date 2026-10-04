// The button that folds a list's last group (stopped sessions, ended runs, finished agents):
// "› Name (n)", or "▾ Name (n)" when open; the open group has the id `controls`.
export function FoldToggle({
  name,
  count,
  open,
  controls,
  onToggle,
}: {
  name: string;
  count: number;
  open: boolean;
  controls: string;
  onToggle: () => void;
}) {
  return (
    <button type="button" className="group-toggle" aria-expanded={open} aria-controls={controls} onClick={onToggle}>
      <span aria-hidden="true">{open ? "▾" : "›"} </span>
      {name} ({count})
    </button>
  );
}
