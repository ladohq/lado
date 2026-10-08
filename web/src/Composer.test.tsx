// The composer's files (docs/design/ui.md, Composer): the paperclip, paste and drop, chips
// with the eye on a file an agent cannot read, the limits from the server, and Send, which
// uploads each file, then sends the message with their names.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { Limits } from "./api";
import { Composer } from "./Composer";
import { TOOLTIP_DELAY_MS } from "./Tooltip";

const LIMITS: Limits = {
  extensions: { png: "image/png", txt: "text/plain", log: "text/plain", pdf: "application/pdf", json: "application/json" },
  text_types: ["application/json"],
  agent_images: ["image/png"],
  max_size: 1000,
  max_files: 3,
  image_limit: 500,
  image_max_side: 8000,
  max_message: 20,
};

type Call = { path: string; body: unknown };

// The API: the limits, an upload answers the artifact of its file name (or `refuse` for a
// name) once `hold` is done, a message answers sent.
function serve(refuse: Record<string, { status: number; detail: string }> = {}, hold: Promise<void> = Promise.resolve()) {
  const calls: Call[] = [];
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    if (path === "/api/limits") return new Response(JSON.stringify(LIMITS));
    const url = new URL(path, "http://lado");
    if (url.pathname.endsWith("/artifacts")) {
      const name = url.searchParams.get("file_name")!;
      await hold;
      calls.push({ path: url.pathname, body: name });
      if (refuse[name]) return new Response(JSON.stringify({ detail: refuse[name].detail }), { status: refuse[name].status });
      const full = `${name.replace(/\.(\w+)$/, "")}-1a2b3c4d${/\.\w+$/.exec(name)?.[0] ?? ""}`;
      return new Response(JSON.stringify({ id: `a-${name}`, full_name: full, name: full, scope: "" }));
    }
    calls.push({ path: url.pathname, body: JSON.parse(String(init?.body)) });
    return new Response(JSON.stringify({ result: "sent" }));
  });
  vi.stubGlobal("fetch", fetch);
  return calls;
}

const made: string[] = [];
const revoked: string[] = [];

beforeEach(() => {
  made.length = 0;
  revoked.length = 0;
  let next = 0;
  vi.stubGlobal("URL", Object.assign(URL, {
    createObjectURL: () => {
      const url = `blob:thumb-${++next}`;
      made.push(url);
      return url;
    },
    revokeObjectURL: (url: string) => revoked.push(url),
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function file(name: string, bytes = 10, type = "") {
  return new File(["x".repeat(bytes)], name, { type });
}

function open(props: Partial<Parameters<typeof Composer>[0]> = {}) {
  return render(
    <section className="chat" aria-label="Chat">
      <p>the feed</p>
      <Composer session="lado" stopped={false} {...props} />
    </section>,
  );
}

const field = () => screen.getByRole("textbox") as HTMLTextAreaElement;
const send = () => screen.getByRole("button", { name: "Send" }) as HTMLButtonElement;
const chips = () => screen.queryAllByRole("listitem").map((one) => one.querySelector(".file-name")?.textContent);

async function pick(...files: File[]) {
  const clip = await screen.findByRole("button", { name: "Attach files" });
  const input = clip.parentElement!.querySelector("input[type=file]") as HTMLInputElement;
  fireEvent.change(input, { target: { files } });
}

test("the paperclip opens the picker for several files; each file is a chip with its size and ×", async () => {
  serve();
  open();
  const clip = await screen.findByRole("button", { name: "Attach files" });
  const input = clip.parentElement!.querySelector("input[type=file]") as HTMLInputElement;
  expect(input.multiple).toBe(true);
  const picked = vi.spyOn(input, "click");
  fireEvent.click(clip);
  expect(picked).toHaveBeenCalled();
  await pick(file("server.log", 900), file("shot.png", 10, "image/png"));
  expect(chips()).toEqual(["server.log", "shot.png"]);
  const [log, shot] = screen.getAllByRole("listitem");
  expect(within(log).getByText("900 B")).toBeTruthy();
  expect(log.querySelector("img")).toBeNull(); // the type's icon
  expect(shot.querySelector("img")?.getAttribute("src")).toBe("blob:thumb-1");
  expect(screen.getByText(/2 files, 910 B/)).toBeTruthy();
  fireEvent.click(within(shot).getByRole("button", { name: "Remove shot.png" }));
  expect(chips()).toEqual(["server.log"]);
  expect(revoked).toEqual(["blob:thumb-1"]);
});

test("Send with files and no text uploads each, then sends the message with their names", async () => {
  const calls = serve();
  open({ to: "w1" });
  await pick(file("a.txt"), file("shot.png", 10, "image/png"));
  expect(send().disabled).toBe(false);
  fireEvent.click(send());
  await waitFor(() => expect(chips()).toEqual([]));
  expect(calls).toEqual([
    { path: "/api/sessions/lado/artifacts", body: "a.txt" },
    { path: "/api/sessions/lado/artifacts", body: "shot.png" },
    { path: "/api/sessions/lado/messages", body: { to: "w1", text: "", artifacts: ["a-1a2b3c4d.txt", "shot-1a2b3c4d.png"] } },
  ]);
  expect(revoked).toEqual(["blob:thumb-1"]);
});

test("a stopped session's composer has its paperclip off", async () => {
  serve();
  open({ stopped: true });
  expect(((await screen.findByRole("button", { name: "Attach files" })) as HTMLButtonElement).disabled).toBe(true);
});

test("the thumbnails' object URLs go when the composer goes", async () => {
  serve();
  const { unmount } = open();
  await pick(file("shot.png", 10, "image/png"));
  unmount();
  expect(revoked).toEqual(["blob:thumb-1"]);
});

test("a pasted image becomes screenshot-<time>.png, a long pasted text a file, a short one stays text", async () => {
  serve();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 8, 5, 13, 7));
  try {
    open();
    await ready();
    const image = file("image.png", 10, "image/png");
    const pasted = fireEvent.paste(field(), { clipboardData: { files: [image], getData: () => "" } });
    expect(pasted).toBe(false); // the browser does not paste it too
    expect(chips()).toEqual(["screenshot-051307.png"]);
    const long = "x".repeat(21);
    expect(fireEvent.paste(field(), { clipboardData: { files: [], getData: () => long } })).toBe(false);
    expect(chips()).toEqual(["screenshot-051307.png", "pasted-051307.txt"]);
    expect(within(screen.getAllByRole("listitem")[1]).getByText("21 B")).toBeTruthy();
    expect(fireEvent.paste(field(), { clipboardData: { files: [], getData: () => "x".repeat(20) } })).toBe(true);
    expect(chips()).toHaveLength(2);
  } finally {
    vi.useRealTimers();
  }
});

// The limits are loaded: the paperclip says them.
const ready = () => screen.findByRole("button", { name: "Attach files" }).then((clip) =>
  waitFor(() => expect(clip.getAttribute("title")).toBe("Attach files: up to 3 files, 1000 B each (or paste, or drop them here)")),
);

test("files dragged over the chat show the drop zone in the composer; dropped there, they are attached", async () => {
  serve();
  open();
  await ready();
  const feed = screen.getByText("the feed");
  const dragged = { types: ["Files"], files: [] as File[] };
  expect(fireEvent.dragEnter(feed, { dataTransfer: dragged })).toBe(false);
  expect(fireEvent.dragOver(feed, { dataTransfer: dragged })).toBe(false); // so it may drop
  const zone = await screen.findByText("Drop to attach · up to 3 files, 1000 B each");
  expect(zone.closest(".composer-box")?.classList.contains("dropping")).toBe(true);
  fireEvent.drop(feed, { dataTransfer: { types: ["Files"], files: [file("server.log")] } });
  expect(chips()).toEqual(["server.log"]);
  expect(screen.queryByText(/Drop to attach/)).toBeNull();
  // text dragged over it is no file: no zone
  fireEvent.dragEnter(feed, { dataTransfer: { types: ["text/plain"], files: [] } });
  expect(screen.queryByText(/Drop to attach/)).toBeNull();
  // leaving the column ends the zone
  fireEvent.dragEnter(feed, { dataTransfer: dragged });
  fireEvent.dragLeave(feed.parentElement!, { dataTransfer: dragged, relatedTarget: document.body });
  expect(screen.queryByText(/Drop to attach/)).toBeNull();
});

const UNSEEN = "The agent sees only this file's name and size";

test("a file an agent cannot read has the crossed-out eye, by the server's types; its hint shows on focus and hover", async () => {
  serve();
  open();
  await ready();
  await pick(
    file("spec.pdf"),
    file("shot.png", 10, "image/png"),
    file("data.json"), // text by the server's text_types
  );
  const [pdf, png, json] = screen.getAllByRole("listitem");
  expect(within(png).queryByRole("button", { name: UNSEEN })).toBeNull();
  expect(within(json).queryByRole("button", { name: UNSEEN })).toBeNull();
  const eye = within(pdf).getByRole("button", { name: UNSEEN });
  fireEvent.focus(eye);
  const hint = await screen.findByRole("tooltip");
  expect(hint.textContent).toBe(
    "The agent sees only this file's name and size. Agents read text and PNG, JPEG, GIF and WebP images.",
  );
  fireEvent.blur(eye);
  expect(screen.queryByRole("tooltip")).toBeNull();
  vi.useFakeTimers();
  fireEvent.mouseEnter(eye);
  vi.advanceTimersByTime(TOOLTIP_DELAY_MS);
  vi.useRealTimers();
  expect((await screen.findByRole("tooltip")).textContent).toMatch(/^The agent sees only/);
});

test("an image over the size an agent is shown has the eye and says why", async () => {
  serve();
  open();
  await ready();
  await pick(file("big.png", 501, "image/png"));
  fireEvent.focus(within(screen.getByRole("listitem")).getByRole("button", { name: UNSEEN }));
  expect((await screen.findByRole("tooltip")).textContent).toBe(
    "The agent sees only this file's name and size: an image over 500 B is not shown to agents.",
  );
});

test("too many files or one too large are refused at the field, naming the file; the rest stay", async () => {
  const calls = serve();
  open();
  await ready();
  await pick(file("a.txt"), file("b.txt"), file("big.log", 1001), file("c.txt"), file("d.txt"));
  expect(chips()).toEqual(["a.txt", "b.txt", "c.txt"]);
  expect(screen.getByRole("alert").textContent).toBe(
    "big.log was not attached: it is 1001 B, the limit is 1000 B. d.txt was not attached: up to 3 files.",
  );
  expect(calls).toEqual([]); // nothing uploaded
});

test("a failed upload keeps the text and a red chip with its reason; Send again uploads only that one, also to another agent", async () => {
  const refuse = { "b.txt": { status: 400, detail: 'session "lado" is stopped' } } as Record<string, { status: number; detail: string }>;
  const calls = serve(refuse);
  const { rerender } = open();
  await ready();
  await pick(file("a.txt"), file("b.txt"));
  fireEvent.change(field(), { target: { value: "see the logs" } });
  fireEvent.click(send());
  const failed = await screen.findByText('session "lado" is stopped');
  expect(failed.closest("li")?.classList.contains("failed")).toBe(true);
  expect(screen.getByRole("alert").textContent).toBe(
    'b.txt was not uploaded: session "lado" is stopped. Remove it, or Send again to try it again.',
  );
  expect(field().value).toBe("see the logs");
  expect(calls.map((one) => one.body)).toEqual(["a.txt", "b.txt"]); // no message
  expect(within(screen.getAllByRole("listitem")[0]).getByText("uploaded")).toBeTruthy();
  delete refuse["b.txt"];
  rerender(
    <section className="chat" aria-label="Chat">
      <p>the feed</p>
      <Composer session="lado" stopped={false} to="w1" />
    </section>,
  );
  fireEvent.click(send());
  await waitFor(() => expect(chips()).toEqual([]));
  expect(calls.slice(2)).toEqual([
    { path: "/api/sessions/lado/artifacts", body: "b.txt" },
    { path: "/api/sessions/lado/messages", body: { to: "w1", text: "see the logs", artifacts: ["a-1a2b3c4d.txt", "b-1a2b3c4d.txt"] } },
  ]);
  expect(field().value).toBe("");
});

test("while files upload the field and chips are locked and a chip shows its progress", async () => {
  let finish = () => {};
  const calls = serve({}, new Promise<void>((done) => (finish = done)));
  open();
  await ready();
  await pick(file("a.txt"));
  fireEvent.click(send());
  expect(await screen.findByRole("progressbar", { name: "Uploading a.txt" })).toBeTruthy();
  expect(field().readOnly).toBe(true);
  expect(screen.queryByRole("button", { name: "Remove a.txt" })).toBeNull();
  expect((screen.getByRole("button", { name: "Attach files" }) as HTMLButtonElement).disabled).toBe(true);
  finish();
  await waitFor(() => expect(calls).toHaveLength(2));
});
