// The selection bar's rules (docs/design/ui.md, Selected text and copy buttons): which
// selection has an area, and the quote it makes. The bar's look, place, Copy and Quote in a
// real browser: tests/ui/test_selection.py.
import { afterEach, expect, test } from "vitest";

import { areaOf, quoteOf } from "./SelectionBar";

afterEach(() => {
  document.getSelection()?.removeAllRanges();
  document.body.innerHTML = "";
});

function page(html: string) {
  document.body.innerHTML = html;
}

// Select from `start` characters into the first text node of `from` to `end` into `to`'s.
function select(from: string, start: number, to: string, end: number): Selection {
  const first = document.querySelector(from)!.firstChild!;
  const last = document.querySelector(to)!.firstChild!;
  const range = document.createRange();
  range.setStart(first, start);
  range.setEnd(last, end);
  const selection = document.getSelection()!;
  selection.removeAllRanges();
  selection.addRange(range);
  return selection;
}

const MESSAGES = `
  <div data-quote="text" data-quote-session="s" id="one"><p id="a">first message</p><p id="b">its second line</p></div>
  <div data-quote="text" data-quote-session="s" id="two"><p id="c">another message</p></div>
  <div class="chrome"><span id="d">Agents</span></div>`;

test("a selection inside one area has it, its quote a Markdown quote", () => {
  page(MESSAGES);
  const selection = select("#a", 6, "#a", 13);
  const area = areaOf(selection);
  expect(area?.id).toBe("one");
  expect(quoteOf(area!, selection)).toBe("> message");
});

test("a selection across two areas, outside any or collapsed has none", () => {
  page(MESSAGES);
  expect(areaOf(select("#a", 0, "#c", 3))).toBeNull();
  expect(areaOf(select("#d", 0, "#d", 3))).toBeNull();
  expect(areaOf(select("#a", 2, "#a", 2))).toBeNull();
  expect(areaOf(null)).toBeNull();
});

test("a selection that ends at the start of what follows, taking none of its text, is still its area's", () => {
  page(MESSAGES);
  const selection = select("#b", 0, "#c", 0); // a triple click on a message's last line
  expect(areaOf(selection)?.id).toBe("one");
  expect(quoteOf(areaOf(selection)!, selection)).toBe("> its second line");
  expect(areaOf(select("#b", 0, "#d", 0))).toBeNull(); // past all of the next message
  page(`<div data-quote="text" data-quote-session="s" id="one"><p id="a">last line</p></div><form><span id="d">to supervisor</span></form>`);
  expect(areaOf(select("#a", 0, "#d", 0))?.id).toBe("one"); // ends in the UI's chrome
  expect(areaOf(select("#a", 0, "#d", 2))).toBeNull(); // takes some of it
});

test("a selection of blanks only has none", () => {
  page(`<div data-quote="text" data-quote-session="s"><p id="a">a   b</p></div>`);
  expect(areaOf(select("#a", 1, "#a", 4))).toBeNull();
});

test("a field, an editable element or a terminal inside an area is none", () => {
  page(`<div data-quote="text" data-quote-session="s">
    <div contenteditable="true" id="e">typed text</div>
    <div class="xterm"><span id="t">$ make lint</span></div>
    <label id="l">label<textarea id="f">x</textarea></label></div>`);
  expect(areaOf(select("#e", 0, "#e", 5))).toBeNull();
  expect(areaOf(select("#t", 0, "#t", 4))).toBeNull();
});
test("a Markdown artifact's quote starts with its name, an earlier record's says so", () => {
  page(`<article data-quote="markdown" data-quote-session="s" data-quote-artifact="task/x/design"><p id="a">AC-2. Quote puts it</p></article>`);
  let selection = select("#a", 0, "#a", 5);
  expect(quoteOf(areaOf(selection)!, selection)).toBe("In task/x/design:\n> AC-2.");
  page(`<article data-quote="markdown" data-quote-session="s" data-quote-artifact="task/x/design" data-quote-earlier><p id="a">AC-2.</p></article>`);
  selection = select("#a", 0, "#a", 5);
  expect(quoteOf(areaOf(selection)!, selection)).toBe("In task/x/design, an earlier record:\n> AC-2.");
});

const CODE = `<table data-quote="code" data-quote-session="s" data-quote-artifact="task/x/notes.py"><tbody>
  <tr data-line="11"><td class="line-number">11</td><td class="line" id="l11">def quote(text):</td></tr>
  <tr data-line="12"><td class="line-number">12</td><td class="line" id="l12">    lines = text.splitlines()</td></tr>
  <tr data-line="13"><td class="line-number">13</td><td class="line" id="l13">    return "x"</td></tr>
  <tr data-line="14"><td class="line-number">14</td><td class="line" id="l14">\`\`\`</td></tr>
</tbody></table>`;

test("a text artifact's quote names its lines and fences them, cut at the selection's ends", () => {
  page(CODE);
  const selection = select("#l12", 4, "#l13", 10);
  expect(quoteOf(areaOf(selection)!, selection)).toBe(
    "In task/x/notes.py (lines 12–13):\n```\nlines = text.splitlines()\n    return\n```",
  );
});

test("one line of a text artifact is (line a); a selection that ends at the next line's start leaves it out", () => {
  page(CODE);
  let selection = select("#l12", 4, "#l12", 9);
  expect(quoteOf(areaOf(selection)!, selection)).toBe("In task/x/notes.py (line 12):\n```\nlines\n```");
  selection = select("#l11", 0, "#l12", 0);
  expect(quoteOf(areaOf(selection)!, selection)).toBe("In task/x/notes.py (line 11):\n```\ndef quote(text):\n```");
});

test("a line that holds backticks gets a longer fence", () => {
  page(CODE);
  const selection = select("#l13", 0, "#l14", 3);
  expect(quoteOf(areaOf(selection)!, selection)).toBe(
    'In task/x/notes.py (lines 13–14):\n````\n    return "x"\n```\n````',
  );
});
