// An artifact's viewer (docs/design/ui.md, Artifacts): its head, and its record's content
// by media type: Markdown without raw HTML, text with line numbers, an image, HTML in a
// sandboxed frame, anything else as facts and a download; a long text read only up to its
// limit; content missing from the store said loudly.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";

import type { ArtifactInfo } from "./api";
import { ArtifactView, TEXT_LIMIT } from "./ArtifactView";
import { artifact, stubLegacyCopy, unstubLegacyCopy } from "./fakes";
import { artifactPath } from "./paths";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  unstubLegacyCopy();
});

function serve(content: BodyInit | null, status = 200) {
  const fetch = vi.fn(async () =>
    status === 200 ? new Response(content) : new Response(JSON.stringify({ detail: content }), { status }),
  );
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function show(shown: ArtifactInfo, latest?: () => void) {
  render(
    <MemoryRouter>
      <ArtifactView session="lado" artifact={shown} record={shown.latest} latest={latest} />
    </MemoryRouter>,
  );
}

const CONTENT = "/api/sessions/lado/records/r1/content";

test("the head names the artifact, its title, author, change and the ways to take it", async () => {
  serve("# Design");
  show(artifact({}, { summary: "the panel is wider" }));
  const head = screen.getByRole("banner");
  expect(head.textContent).toContain("feature/x/design");
  expect(within(head).getByRole("heading", { name: "The design" })).toBeTruthy();
  expect(head.textContent).toContain("architect");
  expect(head.textContent).toContain("the panel is wider");
  expect(within(head).getByRole("link", { name: "Download" }).getAttribute("href")).toBe(`${CONTENT}?download=1`);
  expect(within(head).getByRole("button", { name: "Copy link" })).toBeTruthy();
  expect(within(head).queryByRole("link", { name: "Open in new tab" })).toBeNull();
  await screen.findByRole("heading", { name: "Design" });
});

test("Copy link copies without the Clipboard API, and shows the link only when no copy works", async () => {
  serve("# Design");
  const legacy = stubLegacyCopy();
  show(artifact());
  const copy = within(screen.getByRole("banner")).getByRole("button", { name: "Copy link" });
  copy.focus();
  fireEvent.click(copy);
  await screen.findByText("Link copied");
  const link = `${window.location.origin}${artifactPath("lado", "a1")}`;
  expect(legacy).toEqual([link]);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.querySelector("body > textarea")).toBeNull();
  expect(document.activeElement).toBe(copy);

  stubLegacyCopy(false);
  fireEvent.click(copy);
  const field = await screen.findByRole("dialog", { name: "Link to feature/x/design" });
  expect((within(field).getByRole("textbox", { name: "Link" }) as HTMLInputElement).value).toBe(link);
  await screen.findByRole("heading", { name: "Design" });
});

test("Markdown shows as the chat shows it, with no raw HTML", async () => {
  serve("# Plan\n\nstep <b>one</b><script>window.x = 1</script>\n\n- a\n- b");
  show(artifact());
  await screen.findByRole("heading", { name: "Plan" });
  const body = document.querySelector(".artifact-body")!;
  expect(body.querySelector("b")).toBeNull();
  expect(body.querySelector("script")).toBeNull();
  expect(screen.getAllByRole("listitem").map((one) => one.textContent)).toEqual(["a", "b"]);
});

test("a Markdown table shows as a table with its head and body", async () => {
  serve("# Review\n\n| finding | level |\n| --- | --- |\n| tilde | Minor |\n| ids | Minor |");
  show(artifact());
  await screen.findByRole("heading", { name: "Review" });
  const table = document.querySelector(".artifact-markdown table")!;
  expect([...table.querySelectorAll("thead th")].map((cell) => cell.textContent)).toEqual(["finding", "level"]);
  expect(table.querySelectorAll("tbody tr")).toHaveLength(2);
});

test("text and code show with their line numbers", async () => {
  serve("def f():\n    return 1\n");
  show(artifact({ name: "tool.py", full_name: "feature/x/tool.py" }, { media_type: "text/x-python" }));
  const table = await screen.findByRole("table", { name: "feature/x/tool.py" });
  const rows = within(table).getAllByRole("row").map((row) => [...row.querySelectorAll("td")].map((cell) => cell.textContent));
  expect(rows).toEqual([
    ["1", "def f():"],
    ["2", "    return 1"],
  ]);
});

test("an image shows from its content and opens at full size on a click", async () => {
  const fetch = serve(null);
  show(artifact({ name: "shot.png", full_name: "feature/x/shot.png", title: "The screen" }, { media_type: "image/png" }));
  const image = screen.getByRole("img", { name: "The screen" });
  expect(image.getAttribute("src")).toBe(CONTENT);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(image);
  const full = screen.getByRole("dialog", { name: "feature/x/shot.png at full size" });
  fireEvent.keyDown(full, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("HTML runs in a sandboxed frame that never shares the UI's origin", () => {
  serve(null);
  show(artifact({ name: "mockup.html", full_name: "feature/x/mockup.html" }, { media_type: "text/html" }));
  const frame = screen.getByTitle("feature/x/mockup.html");
  expect(frame.tagName).toBe("IFRAME");
  expect(frame.getAttribute("sandbox")).toBe("allow-scripts");
  expect(frame.getAttribute("src")).toBe(CONTENT);
  expect(screen.getByText(/Runs sandboxed/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "Open in new tab" }).getAttribute("href")).toBe(CONTENT);
});

test("any other type shows its facts and a download", () => {
  serve(null);
  show(artifact({ name: "spec", full_name: "spec", scope: "" }, { media_type: "application/pdf", size: 2048, hash: "abc123" }));
  const facts = screen.getByRole("region", { name: "Not shown in the browser" });
  expect(within(facts).getByText("application/pdf")).toBeTruthy();
  expect(within(facts).getByText("abc123")).toBeTruthy();
  const downloads = screen.getAllByRole("link", { name: "Download" });
  expect(downloads.every((link) => link.getAttribute("href") === `${CONTENT}?download=1`)).toBe(true);
  expect(downloads).toHaveLength(2);
});

test("a long text is read only up to its limit, then the read is cancelled", async () => {
  const chunk = new Uint8Array(256 * 1024).fill(97); // "a" * 256 KB
  let pulled = 0;
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      pulled += 1;
      controller.enqueue(chunk);
    },
    cancel() {
      cancelled = true;
    },
  });
  serve(body);
  show(artifact({}, { media_type: "text/plain", size: 50 * 1024 * 1024 }));
  await screen.findByText(/Shown: the first 1\.0 MB of 50\.0 MB/);
  expect(cancelled).toBe(true);
  expect(pulled * chunk.length).toBeLessThanOrEqual(TEXT_LIMIT + chunk.length);
  const line = await screen.findByRole("table");
  expect(line.textContent?.length).toBeLessThanOrEqual(TEXT_LIMIT + 10);
});

test("content missing from the store is an error that points to lado doctor", async () => {
  serve("content of design is missing from the store (/x)", 500);
  show(artifact());
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("The content of this artifact is missing");
  expect(alert.textContent).toContain("lado doctor");
});

test("a record that is not the latest says the artifact changed since and opens the latest", async () => {
  serve("# Old");
  const latest = vi.fn();
  show(artifact(), latest);
  const banner = screen.getAllByRole("status").find((one) => one.textContent?.includes("changed since"))!;
  expect(banner.textContent).toContain("feature/x/design changed since this record");
  fireEvent.click(within(banner).getByRole("button", { name: "Open latest" }));
  expect(latest).toHaveBeenCalled();
  await waitFor(() => expect(screen.getByRole("heading", { name: "Old" })).toBeTruthy());
});
