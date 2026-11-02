import { useState } from "react";

// One suggestion of a SuggestField: its text, and a muted word after it (e.g. "alias").
export type Suggestion = { value: string; tag?: string };

// Free text with suggestions, the window's own combobox (not a native <datalist>, whose
// popup is the browser's): the drawn arrow opens or closes the whole list; typing and ↓
// open it filtered by what is typed (case-insensitive); ↑↓ move, Enter picks the one
// highlighted (and is otherwise the form's), Esc and leaving the field close it, a click
// picks. Its look: the window's fields (.field input) with a chevron, the list .where-list's.
export function SuggestField({
  id,
  value,
  onValue,
  suggestions,
  arrowLabel,
  listLabel,
  placeholder,
  disabled = false,
}: {
  id: string;
  value: string;
  onValue: (value: string) => void;
  suggestions: Suggestion[];
  arrowLabel: string;
  listLabel: string;
  placeholder?: string;
  disabled?: boolean;
}) {
  // null: closed; else whether the list is filtered by the text (the arrow shows it whole).
  const [open, setOpen] = useState<{ filtered: boolean } | null>(null);
  const [active, setActive] = useState(-1);
  const typed = value.trim().toLowerCase();
  const options =
    open === null
      ? []
      : open.filtered
        ? suggestions.filter((one) => one.value.toLowerCase().includes(typed))
        : suggestions;
  const close = () => {
    setOpen(null);
    setActive(-1);
  };
  const pick = (one: string) => {
    onValue(one);
    close();
  };
  return (
    <div className="suggest-box">
      <input
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={options.length > 0}
        aria-controls={`${id}-list`}
        aria-activedescendant={active >= 0 && options[active] ? `${id}-option-${active}` : undefined}
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        onChange={(event) => {
          onValue(event.target.value);
          setOpen({ filtered: true });
          setActive(-1);
        }}
        onBlur={close}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && options.length === 0) {
            event.preventDefault();
            setOpen({ filtered: true });
            return;
          }
          if (options.length === 0) return;
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const step = event.key === "ArrowDown" ? 1 : -1;
            setActive((at) => (at + step + options.length) % options.length);
          } else if (event.key === "Enter" && options[active]) {
            event.preventDefault();
            pick(options[active].value);
          } else if (event.key === "Escape") {
            event.preventDefault(); // the list closes, not the window
            close();
          }
        }}
      />
      <button
        type="button"
        className="suggest-arrow"
        aria-label={arrowLabel}
        tabIndex={-1}
        disabled={disabled}
        onMouseDown={(event) => event.preventDefault()} // keep the input's focus
        onClick={() => {
          if (open !== null && !open.filtered) close();
          else {
            setOpen({ filtered: false });
            setActive(-1);
          }
          document.getElementById(id)?.focus();
        }}
      >
        <svg viewBox="0 0 12 12" aria-hidden="true">
          <path
            d="M2 4.5l4 4 4-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {options.length > 0 && (
        <ul id={`${id}-list`} role="listbox" aria-label={listLabel} className="where-list suggest-list">
          {options.map((one, i) => (
            <li
              key={one.value}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(event) => {
                event.preventDefault(); // keep the input's focus
                pick(one.value);
              }}
            >
              {one.value}
              {one.tag && <span className="tag">{one.tag}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
