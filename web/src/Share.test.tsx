import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import qrcode from "qrcode-generator";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AccessInfo } from "./api";
import { stubDialogs, stubLegacyCopy } from "./fakes";
import { QrCode } from "./QrCode";
import { cutToken, ShareDialog } from "./Share";

const TOKEN = "Jf3kAbCdEfGhIjKlq8Zw";
const LINK = `http://kaos-mbp.local:8765/?token=${TOKEN}`;

function access(more: Partial<AccessInfo> = {}): AccessInfo {
  return { link: LINK, reason: null, port: 8765, container: false, listen: null, note: null, ...more };
}

// What the server answers; a test changes these.
let answer: AccessInfo;
let renewed: AccessInfo | { status: number; detail: string };
let fetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  answer = access();
  renewed = access({ link: "http://kaos-mbp.local:8765/?token=NEWtoken1234567890xy" });
  fetch = vi.fn(async (path: string, init?: RequestInit) => {
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (path === "/api/access") return json(answer);
    if (path === "/api/access/new-token" && init?.method === "POST") {
      return "status" in renewed ? json({ detail: renewed.detail }, renewed.status) : json(renewed);
    }
    return json({ detail: "not found" }, 404);
  });
  vi.stubGlobal("fetch", fetch);
  stubDialogs();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const shown = async (onClose = () => {}) => {
  render(<ShareDialog onClose={onClose} />);
  return screen.findByRole("dialog", { name: "Open LADO on another device" });
};

test("cutToken shows the token's first and last four characters", () => {
  expect(cutToken("http://h:1/?token=abcdefghijkl")).toBe("http://h:1/?token=abcd…ijkl");
  expect(cutToken("http://h:1/?token=abcdefgh")).toBe("http://h:1/?token=abcdefgh"); // too short to cut
  expect(cutToken("http://h:1/?token=abc")).toBe("http://h:1/?token=abc");
  expect(cutToken("http://h:1/")).toBe("http://h:1/");
});

test("with a link: the warning, the QR code, the cut link, and Copy link copies it whole", async () => {
  const writeText = vi.fn(async () => {});
  vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
  const dialog = await shown();
  await within(dialog).findByRole("img", { name: "QR code of the link" });
  expect(dialog.querySelector(".share-warning")!.textContent).toBe(
    "This link gives full access: sessions, agents' terminals, commands as you. It travels unencrypted (plain HTTP): share it only on a network you trust.",
  );
  expect(within(dialog).getByText("full access").tagName).toBe("STRONG");
  expect(within(dialog).getByText("Scan it with the phone's camera, or send the link.")).toBeTruthy();
  expect(within(dialog).getByText("http://kaos-mbp.local:8765/?token=Jf3k…q8Zw")).toBeTruthy();
  expect(dialog.textContent).not.toContain(TOKEN);
  expect(within(dialog).getByText("Anyone who opened LADO with this link stays in until you make a new one.")).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Copy link" }));
  await within(dialog).findByText("Link copied");
  expect(writeText).toHaveBeenCalledWith(LINK);
  expect(within(dialog).queryByRole("textbox")).toBeNull(); // no field to type an address
});

test("a link the browser does not copy is shown whole, to copy by hand", async () => {
  vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText: vi.fn(async () => Promise.reject(new Error("denied"))) } });
  stubLegacyCopy(false);
  const dialog = await shown();
  fireEvent.click(await within(dialog).findByRole("button", { name: "Copy link" }));
  const field = (await within(dialog).findByRole("textbox", { name: "Text to copy" })) as HTMLTextAreaElement;
  expect(field.value).toBe(LINK);
  expect(within(dialog).queryByText("Link copied")).toBeNull();
});

test("it reads /api/access each time it opens", async () => {
  await shown();
  cleanup();
  await shown();
  expect(fetch.mock.calls.filter(([path]) => path === "/api/access")).toHaveLength(2);
});

test("on loopback outside a container: the command that opens the server to the network", async () => {
  answer = access({ link: null, reason: "loopback" });
  const dialog = await shown();
  await within(dialog).findByText("This LADO server listens on 127.0.0.1 only: other devices cannot reach it.");
  expect(within(dialog).getByText("lado server stop && lado ui --host 0.0.0.0")).toBeTruthy();
  expect(within(dialog).getByText("The sessions keep running; open tabs reconnect.")).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "Copy command" })).toBeTruthy();
  expect(within(dialog).queryByRole("img")).toBeNull();
});

test("on loopback in a container: the .env lines", async () => {
  answer = access({ link: null, reason: "loopback", container: true, listen: "127.0.0.1" });
  const dialog = await shown();
  await within(dialog).findByText("LADO is reachable from this computer only (its port is published on 127.0.0.1).");
  expect(dialog.querySelector(".command")!.textContent).toBe("LADO_LISTEN=0.0.0.0\nLADO_PUBLIC_HOST=<this computer's name>");
  expect(within(dialog).getByRole("button", { name: "Copy lines" })).toBeTruthy();
  expect(within(dialog).queryByRole("img")).toBeNull();
});

test("open to the network in a container without a name: LADO_PUBLIC_HOST", async () => {
  answer = access({ link: null, reason: "no-address", container: true, listen: "0.0.0.0" });
  const dialog = await shown();
  await within(dialog).findByText(
    "LADO is open to your network (LADO_LISTEN=0.0.0.0), but inside its container it cannot learn this computer's address for the link.",
  );
  expect(dialog.querySelector(".command")!.textContent).toBe("LADO_PUBLIC_HOST=<this computer's name>");
  expect(dialog.textContent).toContain("Or publish on one address instead: LADO_LISTEN=<address>.");
  expect(within(dialog).queryByRole("img")).toBeNull();
});

test("unknown: the container's note as the server says it", async () => {
  answer = access({ link: null, reason: "unknown", container: true, note: "the LADO server runs in a container …" });
  const dialog = await shown();
  expect(await within(dialog).findByText("the LADO server runs in a container …")).toBeTruthy();
});

test("New link… asks first; Cancel makes none", async () => {
  const dialog = await shown();
  fireEvent.click(await within(dialog).findByRole("button", { name: "New link…" }));
  expect(within(dialog).getByRole("heading", { name: "Make a new link?" })).toBeTruthy();
  expect(
    within(dialog).getByText(
      "Everyone who opened LADO with the current link — other browsers, phones, people you sent it to — is logged out at once. This browser stays in.",
    ),
  ).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "Make a new link" }).className).toBe("danger");
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(within(dialog).getByRole("heading", { name: "Open LADO on another device" })).toBeTruthy();
  expect(fetch.mock.calls.some(([path]) => path === "/api/access/new-token")).toBe(false);
});

test("Make a new link shows the new link", async () => {
  const dialog = await shown();
  fireEvent.click(await within(dialog).findByRole("button", { name: "New link…" }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Make a new link" }));
  await within(dialog).findByText("http://kaos-mbp.local:8765/?token=NEWt…90xy");
  expect(within(dialog).getByRole("heading", { name: "Open LADO on another device" })).toBeTruthy();
});

test("a new link that is refused says why", async () => {
  renewed = { status: 403, detail: "the Origin http://evil.example is not this server's" };
  const dialog = await shown();
  fireEvent.click(await within(dialog).findByRole("button", { name: "New link…" }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Make a new link" }));
  expect((await within(dialog).findByRole("alert")).textContent).toBe("the Origin http://evil.example is not this server's");
});

test("Close closes it", async () => {
  const onClose = vi.fn();
  const dialog = await shown(onClose);
  fireEvent.click(await within(dialog).findByRole("button", { name: "Close" }));
  expect(onClose).toHaveBeenCalled();
});

test("the QR code is the text's modules, black on white with a quiet zone", () => {
  const text = "http://kaos-mbp.local:8765/?token=abc";
  render(<QrCode text={text} />);
  const svg = screen.getByRole("img", { name: "QR code of the link" });
  const code = qrcode(0, "M");
  code.addData(text);
  code.make();
  const count = code.getModuleCount();
  expect(svg.getAttribute("viewBox")).toBe(`0 0 ${count + 8} ${count + 8}`);
  const dark = new Set<string>();
  for (let row = 0; row < count; row++) for (let col = 0; col < count; col++) if (code.isDark(row, col)) dark.add(`${col + 4},${row + 4}`);
  const drawn = new Set(Array.from(svg.querySelectorAll("g rect"), (rect) => `${rect.getAttribute("x")},${rect.getAttribute("y")}`));
  expect(drawn).toEqual(dark);
  expect(svg.querySelector("rect")!.getAttribute("fill")).toBe("#fff");
  expect(svg.querySelector("g")!.getAttribute("fill")).toBe("#000");
});

test("the page waits while the new link is made", async () => {
  let release = () => {};
  fetch.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === "/api/access/new-token" && init?.method === "POST") {
      await new Promise<void>((done) => (release = done));
      return new Response(JSON.stringify(renewed));
    }
    return new Response(JSON.stringify(answer));
  });
  const dialog = await shown();
  fireEvent.click(await within(dialog).findByRole("button", { name: "New link…" }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Make a new link" }));
  const busy = within(dialog).getByRole("button", { name: "Making…" }) as HTMLButtonElement;
  expect(busy.disabled).toBe(true);
  release();
  await waitFor(() => expect(within(dialog).queryByRole("button", { name: "Making…" })).toBeNull());
});
