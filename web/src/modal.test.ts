import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { createElement, useRef } from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { stubDialogs } from "./fakes";
import { useModal } from "./modal";

function Window() {
  const dialog = useRef<HTMLDialogElement>(null);
  useModal(dialog);
  return createElement("dialog", { ref: dialog, "aria-label": "Window" });
}

beforeEach(stubDialogs);
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

test("a window opens modal", () => {
  const { container } = render(createElement(Window));
  expect(container.querySelector("dialog")?.hasAttribute("open")).toBe(true);
});

// The browser gives the focus back only to a close() of a window still in the page.
test("a window closes while it is still in the page", () => {
  const inPage: boolean[] = [];
  vi.spyOn(HTMLDialogElement.prototype, "close").mockImplementation(function (this: HTMLDialogElement) {
    inPage.push(this.isConnected);
  });
  render(createElement(Window)).unmount();
  expect(inPage).toEqual([true]);
});

test("only modal.ts shows a window, so that every window gives the focus back", () => {
  const folder = dirname(fileURLToPath(import.meta.url));
  const others = readdirSync(folder)
    .filter((name) => /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name))
    .filter((name) => name !== "modal.ts" && name !== "fakes.ts")
    .filter((name) => /\.showModal\(/.test(readFileSync(join(folder, name), "utf8")));
  expect(others).toEqual([]);
});
