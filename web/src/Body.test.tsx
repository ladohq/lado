// A text as Markdown (docs/design/ui.md, Look of the feed): GitHub-flavoured Markdown in
// every body, the human's line breaks kept, no raw HTML, footnotes of one body its own.
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { Body } from "./ChatText";
import { stubLegacyCopy, unstubLegacyCopy } from "./fakes";

afterEach(cleanup);

const TABLE = "| name | state |\n| :--- | ---: |\n| w1 | done |\n| w2 | busy |";

function shown(text: string, breaks = false) {
  return render(<Body text={text} breaks={breaks} />).container;
}

test("a GFM table renders as a table with its head and body, in a frame of its own", () => {
  const body = shown(TABLE);
  const table = body.querySelector(".md-table > table")!;
  expect(table).toBeTruthy();
  expect([...table.querySelectorAll("thead th")].map((cell) => cell.textContent)).toEqual(["name", "state"]);
  expect([...table.querySelectorAll("tbody tr")].map((row) => row.textContent)).toEqual(["w1done", "w2busy"]);
});

test("the human's text keeps its single line breaks and still renders a table", () => {
  const body = shown(`first\nsecond\n\n${TABLE}`, true);
  expect(body.querySelector("p")!.querySelectorAll("br")).toHaveLength(1);
  expect(body.querySelectorAll("tbody tr")).toHaveLength(2);
});

test("a fenced code block has Copy code, which copies its code exactly; inline code has none", async () => {
  const written: string[] = [];
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: async (text: string) => void written.push(text) },
  });
  const body = render(<Body text={"Run `make` or:\n\n```sh\nuv run pytest -m ui\n  --tb=short\n```"} />);
  const buttons = body.getAllByRole("button", { name: "Copy code" });
  expect(buttons).toHaveLength(1);
  expect(buttons[0].closest(".code-block")?.querySelector("pre")).toBeTruthy();
  fireEvent.click(buttons[0]);
  expect(await body.findByText("Copied")).toBeTruthy();
  expect(written).toEqual(["uv run pytest -m ui\n  --tb=short"]);
  delete (navigator as { clipboard?: unknown }).clipboard;
});

test("when no copy works, the code to copy by hand keeps its lines", async () => {
  stubLegacyCopy(false);
  const body = render(<Body text={"```\nfirst\nsecond\n```"} />);
  fireEvent.click(body.getByRole("button", { name: "Copy code" }));
  const field = (await body.findByRole("textbox", { name: "Code" })) as HTMLTextAreaElement;
  expect(field.value).toBe("first\nsecond");
  unstubLegacyCopy();
});

test("a column's alignment reaches its cells", () => {
  const cells = shown(TABLE).querySelectorAll("tbody tr:first-child td");
  expect((cells[0] as HTMLElement).style.textAlign).toBe("left");
  expect((cells[1] as HTMLElement).style.textAlign).toBe("right");
});

test("a task list renders checkboxes the human cannot tick", () => {
  const boxes = [...shown("- [x] built\n- [ ] checked").querySelectorAll("input[type=checkbox]")] as HTMLInputElement[];
  expect(boxes.map((box) => [box.checked, box.disabled])).toEqual([
    [true, true],
    [false, true],
  ]);
});

test("only a double tilde strikes through", () => {
  expect(shown("~~gone~~").querySelector("del")!.textContent).toBe("gone");
  expect(shown("5~10 and 20~30 min").querySelector("del")).toBeNull();
});

test("a bare URL is a link", () => {
  expect(shown("see https://example.com/x for more").querySelector("a")!.getAttribute("href")).toBe("https://example.com/x");
});

test("raw HTML is left out", () => {
  const body = shown("step <b>one</b><script>window.x = 1</script>\n\n<div>block</div>");
  expect(body.querySelector("b")).toBeNull();
  expect(body.querySelector("script")).toBeNull();
  expect(body.querySelector(".chat-body div")).toBeNull();
});

test("two bodies' footnotes have ids of their own, and each link points to its own", () => {
  const page = render(
    <>
      <Body text={"one[^1]\n\n[^1]: first"} />
      <Body text={"two[^1]\n\n[^1]: second"} />
    </>,
  ).container;
  const links = [...page.querySelectorAll("sup a")];
  expect(links).toHaveLength(2);
  const targets = links.map((link) => link.getAttribute("href")!.slice(1));
  expect(new Set(targets).size).toBe(2);
  const notes = targets.map((id) => page.ownerDocument.getElementById(id)!.textContent);
  expect(notes[0]).toContain("first");
  expect(notes[1]).toContain("second");
});
