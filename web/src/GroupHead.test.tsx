// A list group's heading (docs/design/ui.md, Structure: List and page): one look for every
// list, a band in the group's tone, folding when the list asks for it.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { GroupHead, type Tone } from "./GroupHead";

afterEach(cleanup);

test("without folding: a heading of the group's name and count in its tone, no button, no chevron", () => {
  render(<GroupHead nameId="g-name" name="Active" count={3} tone="done" />);
  const heading = screen.getByRole("heading", { level: 3 });
  expect(heading.className).toContain("group-head");
  expect(heading.className).toContain("tone-done");
  expect(heading.querySelector(".group-name")!.id).toBe("g-name");
  expect(heading.querySelector(".group-name")!.textContent).toBe("Active");
  expect(heading.querySelector(".group-count")!.textContent).toBe("3");
  expect(screen.queryByRole("button")).toBeNull();
  expect(heading.querySelector("svg")).toBeNull();
});

test("the tone is neutral unless given; each tone has its class", () => {
  const { rerender } = render(<GroupHead nameId="g" name="Ended" count={0} />);
  expect(screen.getByRole("heading").className).toContain("tone-neutral");
  for (const tone of ["human", "done", "neutral"] as Tone[]) {
    rerender(<GroupHead nameId="g" name="Ended" count={0} tone={tone} />);
    expect(screen.getByRole("heading").className).toContain(`tone-${tone}`);
  }
});

function Folding() {
  const [open, setOpen] = useState(true);
  return (
    <section>
      <GroupHead nameId="r-name" name="Running" count={2} tone="done" fold={{ open, controls: "r-list", onToggle: () => setOpen(!open) }} />
      <ul id="r-list" hidden={!open} />
    </section>
  );
}

test("folding: the heading holds a button with the chevron, aria-expanded and aria-controls of an element there", () => {
  render(<Folding />);
  const button = screen.getByRole("button", { name: "Running 2" });
  expect(button.closest("h3")).toBeTruthy();
  expect(button.querySelector("svg")).toBeTruthy();
  expect(button.getAttribute("aria-expanded")).toBe("true");
  expect(document.getElementById(button.getAttribute("aria-controls")!)).toBeTruthy();
  fireEvent.click(button);
  expect(button.getAttribute("aria-expanded")).toBe("false");
  expect(document.getElementById(button.getAttribute("aria-controls")!)).toBeTruthy(); // still there, folded
  fireEvent.click(button);
  expect(button.getAttribute("aria-expanded")).toBe("true");
});

test("an action: a button of its own after the fold button, in the band; pressing it does not fold the group", () => {
  const acted = vi.fn();
  const toggled = vi.fn();
  render(
    <GroupHead
      nameId="s-name"
      name="Stopped"
      count={7}
      fold={{ open: false, controls: "s-list", onToggle: toggled }}
      action={
        <button type="button" className="group-action" aria-label="Forget stopped sessions…" onClick={acted} />
      }
    />,
  );
  const heading = screen.getByRole("heading", { level: 3 });
  const buttons = within(heading).getAllByRole("button");
  expect(buttons.map((button) => button.getAttribute("aria-label") ?? button.textContent)).toEqual([
    "Stopped 7",
    "Forget stopped sessions…",
  ]);
  fireEvent.click(buttons[1]);
  expect(acted).toHaveBeenCalledOnce();
  expect(toggled).not.toHaveBeenCalled();
  expect(buttons[0].getAttribute("aria-expanded")).toBe("false");
});

test("an action without folding is drawn after the count", () => {
  render(<GroupHead nameId="a" name="Active" count={1} action={<button type="button">Act</button>} />);
  const heading = screen.getByRole("heading", { level: 3 });
  expect(heading.lastElementChild!.textContent).toBe("Act");
});
