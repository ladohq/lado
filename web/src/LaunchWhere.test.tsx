// Where's combobox on its own (LaunchWhere.tsx): what it shows closed, its list's groups and
// the keys that open, move, pick and close it.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, expect, test, vi } from "vitest";

import type { RecentFolder, SessionInfo } from "./api";
import { PlaceBox, type Shown } from "./LaunchWhere";

afterEach(cleanup);

const session = (name: string, repo: string) =>
  ({ name, repo, status: "stopped", running_since: null, stopped_at: null }) as unknown as SessionInfo;

const RECENT: RecentFolder[] = [
  { path: "/w/webapp", session: session("webapp", "/w/webapp"), project: null },
  { path: "/w/projects/shop/backend", session: session("shop-backend", "/w/projects/shop/backend"), project: { id: "shop", title: "Shop", repo: "backend" } },
];

function box(shown: Shown = { icon: "folder", name: "webapp", sub: "/w/webapp" }) {
  const calls = { recent: vi.fn(), path: vi.fn(), way: vi.fn() };
  render(
    <PlaceBox
      id="where"
      shown={shown}
      recent={RECENT}
      onRecent={calls.recent}
      onPath={calls.path}
      onWay={calls.way}
      disabled={false}
      inputRef={createRef<HTMLInputElement>()}
    />,
  );
  return { input: screen.getByRole("combobox"), calls };
}

test("closed, it shows the place's name and its secondary on one line, the two as its tooltip", () => {
  box({ icon: "project", name: "backend", sub: "in project Shop" });
  expect((screen.getByRole("combobox") as HTMLInputElement).value).toBe("backend");
  const sub = screen.getByText("in project Shop", { selector: ".place-text .place-sub" });
  expect(sub.closest(".place-box")!.getAttribute("title")).toBe("backend — in project Shop");
  expect(document.querySelector(".place-badge")).toBeNull();
  expect(screen.getByRole("combobox").getAttribute("aria-expanded")).toBe("false");
});

test("a place without a secondary has its name alone as its tooltip", () => {
  box({ icon: "link", name: "Clone from URL" });
  expect(document.querySelector(".place-sub")).toBeNull();
  expect(document.querySelector(".place-box")!.getAttribute("title")).toBe("Clone from URL");
});

test("Alt+Down opens it on Recent then Somewhere else; arrows move, Enter picks a way", () => {
  const { input, calls } = box();
  fireEvent.keyDown(input, { key: "ArrowDown", altKey: true });
  const list = screen.getByRole("listbox", { name: "Places" });
  expect(input.getAttribute("aria-controls")).toBe(list.id);
  const options = within(list).getAllByRole("option");
  expect(options.map((one) => one.textContent)).toEqual([
    "webapp/w/webapp",
    "backendin project Shop",
    "Other folder…",
    "Clone from URL…",
    "New empty folder…",
    "Project…",
  ]);
  expect(input.getAttribute("aria-activedescendant")).toBe(options[0].id);
  for (let i = 0; i < 3; i++) fireEvent.keyDown(input, { key: "ArrowDown" });
  expect(options[3].getAttribute("aria-selected")).toBe("true");
  fireEvent.keyDown(input, { key: "Enter" });
  expect(calls.way).toHaveBeenCalledWith("url");
  expect(screen.queryByRole("listbox")).toBeNull();
});

test("a project item is picked as itself; Esc closes the list and is taken", () => {
  const { input, calls } = box();
  fireEvent.keyDown(input, { key: "ArrowDown" });
  fireEvent.mouseDown(screen.getByRole("option", { name: /^backend/ }));
  expect(calls.recent).toHaveBeenCalledWith(RECENT[1]);
  fireEvent.keyDown(input, { key: "ArrowDown" });
  const parent = vi.fn((event: KeyboardEvent) => event.defaultPrevented);
  document.addEventListener("keydown", parent);
  fireEvent.keyDown(input, { key: "Escape" });
  document.removeEventListener("keydown", parent);
  expect(parent).toHaveReturnedWith(true);
  expect(screen.queryByRole("listbox")).toBeNull();
});

test("a typed letter opens it filtered by name; a typed path offers Use folder", () => {
  const { input, calls } = box();
  fireEvent.keyDown(input, { key: "k" });
  expect((input as HTMLInputElement).value).toBe("k");
  expect(screen.getAllByRole("option")[0].textContent).toBe("backendin project Shop");
  fireEvent.change(input, { target: { value: "/tmp/x" } });
  expect(screen.getAllByRole("option").map((one) => one.textContent)).toEqual(["Use folder /tmp/x"]);
  fireEvent.keyDown(input, { key: "Enter" });
  expect(calls.path).toHaveBeenCalledWith("/tmp/x");
});
