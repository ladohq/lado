// The human's files, one module for the composer and the waiting card's fields
// (docs/design/ui.md, Composer): what the limits refuse, the upload of what is not uploaded
// yet, and a drop zone that leaves a region to its own fields.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { Limits } from "./api";
import { attachFiles, FileChips, uploadFiles, useDropZone, type Attached } from "./attachFiles";

const LIMITS: Limits = {
  extensions: { png: "image/png", txt: "text/plain" },
  text_types: [],
  agent_images: ["image/png"],
  max_size: 1000,
  max_files: 2,
  image_limit: 500,
  image_max_side: 8000,
  max_message: 20,
  max_title: 80,
};

beforeEach(() => {
  let next = 0;
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => `blob:thumb-${++next}`, revokeObjectURL: () => {} }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const file = (name: string, bytes = 10, type = "") => new File(["x".repeat(bytes)], name, { type });

test("attaching over the limits names each refused file and keeps the rest", () => {
  const { added, problem } = attachFiles([file("big.txt", 2000), file("a.txt"), file("b.png", 10, "image/png")], 1, LIMITS);
  expect(added.map((one) => [one.name, one.thumb, one.state])).toEqual([["a.txt", "blob:thumb-1", "ready"]]);
  expect(problem).toBe(
    "big.txt was not attached: it is 2.0 KB, the limit is 1000 B. b.png was not attached: up to 2 files.",
  );
  expect(attachFiles([file("c.png", 10, "image/png")], 0, LIMITS)).toMatchObject({ added: [{ thumb: "blob:thumb-2" }], problem: null });
});

test("a chip attached before the limits load takes its type when they load", () => {
  const { added } = attachFiles([file("shot.png", 10, "image/png"), file("server.log"), file("spec.pdf")], 0, null);
  const chips = (limits: Limits | null) => <FileChips files={added} limits={limits} locked={false} remove={() => {}} />;
  const unseen = () => screen.queryAllByRole("button", { name: "The agent sees only this file's name and size" });
  const view = render(chips(null));
  expect(unseen()).toHaveLength(0);
  expect(view.container.querySelectorAll("img")).toHaveLength(0);
  view.rerender(
    chips({ ...LIMITS, extensions: { png: "image/png", log: "text/plain", pdf: "application/pdf" }, max_files: 10 }),
  );
  expect(unseen().map((one) => one.closest("li")?.querySelector(".file-name")?.textContent)).toEqual(["spec.pdf"]);
  const images = Array.from(view.container.querySelectorAll("img"));
  expect(images.map((one) => [one.closest("li")?.querySelector(".file-name")?.textContent, one.getAttribute("src")])).toEqual([
    ["shot.png", "blob:thumb-1"],
  ]);
});

test("an upload that fails stops the answer with its reason; the next one uploads only the failed file", async () => {
  const uploads: string[] = [];
  let refuse = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const name = new URL(path, "http://lado").searchParams.get("file_name")!;
      uploads.push(name);
      if (name === "b.txt" && refuse) return new Response(JSON.stringify({ detail: "disk full" }), { status: 500 });
      return new Response(JSON.stringify({ full_name: `${name}-1` }));
    }),
  );
  let files: Attached[] = attachFiles([file("a.txt"), file("b.txt")], 0, LIMITS).added;
  const setFiles = (update: (now: Attached[]) => Attached[]) => {
    files = update(files);
  };
  expect(await uploadFiles("lado", files, setFiles, "answer again")).toEqual({
    problem: "b.txt was not uploaded: disk full. Remove it, or answer again to try it again.",
  });
  expect(files.map((one) => [one.state, one.uploaded, one.reason])).toEqual([
    ["uploaded", "a.txt-1", null],
    ["failed", null, "disk full"],
  ]);
  refuse = false;
  expect(await uploadFiles("lado", files, setFiles, "answer again")).toEqual({ names: ["a.txt-1", "b.txt-1"] });
  expect(uploads).toEqual(["a.txt", "b.txt", "b.txt"]);
});

function Area({ attach }: { attach: (files: File[]) => void }) {
  const inner = useRef<HTMLParagraphElement>(null);
  const [got, setGot] = useState(0);
  const dropping = useDropZone(inner, (files) => {
    setGot(files.length);
    attach(files);
  }, { closest: ".chat", ignoreInside: ".waiting-card" });
  return (
    <section className="chat">
      <p ref={inner}>the feed {dropping ? "dropping" : ""} {got}</p>
      <div className="waiting-card">
        <p>a question</p>
      </div>
    </section>
  );
}

test("a drop zone leaves files dropped inside the region it ignores", () => {
  const attach = vi.fn();
  render(<Area attach={attach} />);
  const dragged = { types: ["Files"], files: [file("a.txt")] };
  fireEvent.dragOver(screen.getByText(/the feed/), { dataTransfer: dragged });
  expect(screen.getByText(/the feed/).textContent).toContain("dropping");
  act(() => {
    fireEvent.dragOver(screen.getByText("a question"), { dataTransfer: dragged });
  });
  expect(screen.getByText(/the feed/).textContent).not.toContain("dropping");
  fireEvent.drop(screen.getByText("a question"), { dataTransfer: dragged });
  expect(attach).not.toHaveBeenCalled();
  fireEvent.drop(screen.getByText(/the feed/), { dataTransfer: dragged });
  expect(attach).toHaveBeenCalledTimes(1);
});
