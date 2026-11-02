import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { SuggestField, type Suggestion } from "./SuggestField";

afterEach(cleanup);

const SUGGESTIONS: Suggestion[] = [
  { value: "opus", tag: "alias" },
  { value: "sonnet", tag: "alias" },
  { value: "kilo/small" },
  { value: "kilo/large" },
];

// The field in a form, as the launch window has it: what Enter submits is counted.
function show(first = "") {
  const submitted = vi.fn();
  function Field() {
    const [value, setValue] = useState(first);
    return (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submitted(value);
        }}
      >
        <label htmlFor="m">Model</label>
        <SuggestField
          id="m"
          value={value}
          onValue={setValue}
          suggestions={SUGGESTIONS}
          arrowLabel="Show the models"
          listLabel="Models"
        />
      </form>
    );
  }
  render(<Field />);
  return { field: screen.getByRole("combobox", { name: "Model" }) as HTMLInputElement, submitted };
}

const shown = () => screen.queryAllByRole("option").map((one) => one.textContent);

test("the arrow opens the whole list with its tags, and closes it", () => {
  const { field } = show("kilo/large");
  expect(field.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(screen.getByRole("button", { name: "Show the models" }));
  expect(shown()).toEqual(["opusalias", "sonnetalias", "kilo/small", "kilo/large"]);
  expect(field.getAttribute("aria-expanded")).toBe("true");
  expect(screen.getByRole("listbox", { name: "Models" }).id).toBe(field.getAttribute("aria-controls"));
  fireEvent.click(screen.getByRole("button", { name: "Show the models" }));
  expect(shown()).toEqual([]);
});

test("typing opens the list filtered by what is typed, in any case; free text is kept", () => {
  const { field } = show();
  fireEvent.change(field, { target: { value: "LA" } });
  expect(shown()).toEqual(["kilo/large"]);
  fireEvent.change(field, { target: { value: "nope" } });
  expect(shown()).toEqual([]);
  expect(field.value).toBe("nope");
});

test("↓ opens the list, ↑↓ move, Enter picks the highlighted one without submitting", () => {
  const { field, submitted } = show("kilo");
  fireEvent.keyDown(field, { key: "ArrowDown" });
  expect(shown()).toEqual(["kilo/small", "kilo/large"]);
  fireEvent.keyDown(field, { key: "ArrowDown" });
  fireEvent.keyDown(field, { key: "ArrowDown" });
  const active = screen.getByRole("option", { selected: true });
  expect(active.textContent).toBe("kilo/large");
  expect(field.getAttribute("aria-activedescendant")).toBe(active.id);
  fireEvent.keyDown(field, { key: "ArrowUp" });
  expect(screen.getByRole("option", { selected: true }).textContent).toBe("kilo/small");
  const enter = fireEvent.keyDown(field, { key: "Enter" });
  expect(enter).toBe(false); // prevented: the pick is not the form's Enter
  expect(field.value).toBe("kilo/small");
  expect(shown()).toEqual([]);
  expect(submitted).not.toHaveBeenCalled();
});

test("Enter with nothing highlighted is the form's", () => {
  const { field } = show("kilo");
  fireEvent.change(field, { target: { value: "kilo/" } });
  expect(fireEvent.keyDown(field, { key: "Enter" })).toBe(true);
});

test("Esc and leaving the field close the list; a click picks", () => {
  const { field } = show();
  fireEvent.change(field, { target: { value: "us" } });
  expect(shown()).toEqual(["opusalias"]);
  expect(fireEvent.keyDown(field, { key: "Escape" })).toBe(false);
  expect(shown()).toEqual([]);
  fireEvent.change(field, { target: { value: "s" } });
  fireEvent.blur(field);
  expect(shown()).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "Show the models" }));
  fireEvent.mouseDown(screen.getByRole("option", { name: /sonnet/ }));
  expect(field.value).toBe("sonnet");
  expect(shown()).toEqual([]);
});
