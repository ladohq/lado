// The Report a bug page (docs/design/ui.md, Report a bug).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { BugReport } from "./api";
import { ReportBug } from "./ReportBug";
import { browserLine } from "./SystemPanel";

const REPORT: BugReport = {
  title: "KeyError at loop",
  text: "### What happened\n\n### LADO system info\n- Browser: Firefox 131 on Linux\n\n### LADO errors (last 30 days, 1 kind)\n- KeyError at loop, once, 2026-10-14, LADO 0.38.0\n",
  url: "https://github.com/ladohq/lado/issues/new?title=KeyError%20at%20loop&body=x",
  left_out: 0,
};

let answer: () => Response;

function serve() {
  const fetch = vi.fn(async () => answer());
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

beforeEach(() => {
  answer = () => new Response(JSON.stringify(REPORT));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("the page loads the report with its browser line and shows the warning, the text and the link", async () => {
  const fetch = serve();
  render(<ReportBug />);
  expect(screen.getByText("Loading…")).toBeTruthy();
  const link = await screen.findByRole("link", { name: "Open a new issue on GitHub ↗" });
  expect(link.getAttribute("href")).toBe(REPORT.url);
  expect(link.getAttribute("target")).toBe("_blank");
  expect(link.getAttribute("rel")).toBe("noreferrer");
  expect(document.querySelector("pre.log")?.textContent).toBe(REPORT.text);
  expect(screen.getByText(/Nothing is sent until you submit it there/)).toBeTruthy();
  const privately = screen.getByRole("link", { name: "private reporting" });
  expect(privately.getAttribute("href")).toBe("https://github.com/ladohq/lado/security/advisories/new");
  const [path] = fetch.mock.calls[0] as unknown as [string];
  const line = browserLine(navigator.userAgent);
  expect(path).toBe(`/api/bug-report?browser=${encodeURIComponent(line)}`);
});

test("Copy text copies the whole report", async () => {
  serve();
  const writeText = vi.fn(async () => {});
  vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
  render(<ReportBug />);
  fireEvent.click(await screen.findByRole("button", { name: "Copy text" }));
  expect(await screen.findByText("Report copied")).toBeTruthy();
  expect(writeText).toHaveBeenCalledWith(REPORT.text);
});

test("a failed load shows why", async () => {
  answer = () => new Response(JSON.stringify({ detail: "lado.db has schema 99" }), { status: 503 });
  serve();
  render(<ReportBug />);
  expect((await screen.findByRole("alert")).textContent).toBe("lado.db has schema 99");
  expect(screen.queryByRole("link", { name: "Open a new issue on GitHub ↗" })).toBeNull();
});
