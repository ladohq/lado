// Settings → Git servers (GitServers.tsx) against a fake API: the rows and panels, Check and
// its lines, Replace token, the commit author with Undo, Remove server, Add's states, one
// result line at a time and where the focus goes.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { GitServerAdded, GitServerCheck, GitServerChecked, GitServerInfo, GitServers } from "./api";
import { GitServersPage, TIPS } from "./GitServers";

const TOKEN = "glpat-CANARY-vitest";
const KINDS = [
  { name: "github", title: "GitHub", token_path: "/settings/tokens", scopes: "scope repo" },
  {
    name: "gitlab",
    title: "GitLab",
    token_path: "/-/user_settings/personal_access_tokens",
    scopes: "scopes read_repository, write_repository, read_api",
  },
];
const CORP: GitServerInfo = {
  address: "https://gitlab.corp.example",
  host: "gitlab.corp.example",
  kind: "gitlab",
  kind_title: "GitLab",
  login: "a.sample",
  has_token: true,
  author_name: "Sample Name",
  author_email: "sample.name@corp.example.com",
};
const GHE: GitServerInfo = {
  address: "https://ghe.example.com:8443",
  host: "ghe.example.com:8443",
  kind: "github",
  kind_title: "GitHub",
  login: null,
  has_token: true,
  author_name: null,
  author_email: null,
};

const nothing: GitServerCheck = {
  address: null,
  hint: null,
  token_page: null,
  scopes: null,
  choose_kind: false,
  unchecked: null,
  saved: false,
  refusals: [],
  warnings: [],
};

function looksLike(address: string, kind: "gitlab" | "github"): GitServerCheck {
  const found = KINDS.find((k) => k.name === kind)!;
  return { ...nothing, address, hint: kind, token_page: address + found.token_path, scopes: found.scopes };
}

function checked(server: GitServerInfo, found: Partial<GitServerChecked>): GitServerChecked {
  return {
    outcome: "ok",
    kind: server.kind,
    login: null,
    missing_scopes: [],
    rights_checked: true,
    was_checked: true,
    message: "",
    hint: "",
    server,
    ...found,
  };
}

const added = (server: GitServerInfo, more: Partial<GitServerAdded> = {}): GitServerAdded => ({
  server,
  line: "",
  replaced: false,
  warnings: [],
  warning: null,
  missing_scopes: [],
  ...more,
});

type Call = { method: string; path: string; body: Record<string, unknown> | undefined };

class Fake {
  servers: GitServerInfo[] = [];
  calls: Call[] = [];
  checks: Record<string, GitServerCheck> = {};
  saved: Record<string, () => Response> = {}; // a saved server's check, by host
  add: (body: Record<string, unknown>) => Response = () => new Response("{}", { status: 500 });
  removal: string | null = null;
  authorHeld: (() => Response) | null = null; // while set, a change of the author waits for it
  author(method: string, path: string, body: Record<string, unknown> | undefined): Response {
    const host = decodeURIComponent(path.slice("/api/git-servers/".length, -"/author".length));
    const server = this.servers.find((s) => s.host === host)!;
    const set = method === "PUT";
    const saved = {
      ...server,
      author_name: set ? String(body!.name).trim() : null,
      author_email: set ? String(body!.email).trim() : null,
    };
    this.servers = this.servers.map((s) => (s.host === host ? saved : s));
    return new Response(JSON.stringify({ server: saved, line: "" }), { status: 200 });
  }
  install() {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        const body = init?.body ? JSON.parse(String(init.body)) : undefined;
        this.calls.push({ method, path, body });
        const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
        const listing = (): GitServers => ({ servers: this.servers, kinds: KINDS });
        if (path === "/api/git-servers" && method === "GET") return json(listing());
        if (path === "/api/git-servers/check") return json(this.checks[(body as { address: string }).address] ?? nothing);
        if (path === "/api/git-servers" && method === "POST") return this.add(body!);
        if (path.endsWith("/author")) {
          if (this.authorHeld) await this.authorHeld(); // answers once let go
          return this.author(method, path, body);
        }
        if (path.endsWith("/check") && method === "POST") {
          const host = decodeURIComponent(path.slice("/api/git-servers/".length, -"/check".length));
          return this.saved[host]();
        }
        if (path.startsWith("/api/git-servers/") && method === "DELETE") {
          const host = decodeURIComponent(path.slice("/api/git-servers/".length));
          this.servers = this.servers.filter((s) => s.host !== host);
          return json({ ...listing(), warning: this.removal });
        }
        return json({ detail: "no such route" }, 404);
      }),
    );
  }
}

let fake: Fake;

beforeEach(() => {
  fake = new Fake();
  fake.install();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function mount() {
  render(
    <MemoryRouter>
      <GitServersPage />
    </MemoryRouter>,
  );
  await screen.findByRole("button", { name: "About Servers" });
}

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const refused = (message: string, field: string, choose_kind = false) =>
  json({ detail: { message, hint: "", field, warnings: [], choose_kind } }, 400);
const button = (name: string | RegExp) => screen.getByRole("button", { name });
const press = (name: string | RegExp) => fireEvent.click(button(name));
const type = (field: HTMLElement, value: string) => fireEvent.change(field, { target: { value } });
const results = () => document.querySelectorAll(".gx-result, .mx-done");
const openRow = (server: GitServerInfo) => press(server.address);
const row = (server: GitServerInfo) => button(server.address).closest("li.mx-src") as HTMLElement;

// The list and the rows.

test("a closed row says the address, the kind, the login and the author; an open one its panel", async () => {
  fake.servers = [CORP, GHE, { ...GHE, address: "http://git.lan", host: "git.lan", kind_title: "GitLab", has_token: false }];
  await mount();
  expect(within(row(CORP)).getByText("signed in as a.sample")).toBeTruthy();
  expect(within(row(CORP)).getByText(/commits as Sample Name <sample.name@corp.example.com>/)).toBeTruthy();
  expect(within(row(GHE)).getByText("⚠ not checked")).toBeTruthy();
  const lan = row({ ...GHE, address: "http://git.lan" });
  expect(within(lan).getByText("⚠ token missing")).toBeTruthy();
  expect(within(lan).getByText("plain http")).toBeTruthy();
  expect(button(CORP.address).getAttribute("aria-expanded")).toBe("false");
  expect(button(CORP.address).getAttribute("aria-describedby")).toBeTruthy();
  openRow(CORP);
  expect(button(CORP.address).getAttribute("aria-expanded")).toBe("true");
  expect(button(CORP.address).getAttribute("aria-describedby")).toBeNull();
  const panel = within(row(CORP));
  expect(panel.getByText("a.sample", { selector: "b" })).toBeTruthy();
  expect(panel.getByRole("button", { name: `Check ${CORP.address}` })).toBeTruthy();
  expect(panel.getByRole("button", { name: `Replace the token of ${CORP.address}` })).toBeTruthy();
  expect(panel.getByRole("button", { name: `Edit the commit author of ${CORP.address}` })).toBeTruthy();
  expect(panel.getByRole("button", { name: `Remove the commit author of ${CORP.address}` })).toBeTruthy();
  expect(panel.getByRole("button", { name: `Remove ${CORP.address}` }).textContent).toBe("Remove server");
});

test("a missing token offers Replace token alone, as the main button", async () => {
  const gone = { ...CORP, has_token: false };
  fake.servers = [gone];
  await mount();
  openRow(gone);
  expect(within(row(gone)).getByText("⚠ Token missing")).toBeTruthy();
  expect(screen.queryByRole("button", { name: `Check ${CORP.address}` })).toBeNull();
  expect(button(`Replace the token of ${CORP.address}`).className).toBe("primary");
});

test("none saved: one line and + Add server; the Servers tip opens and keeps the focus", async () => {
  await mount();
  expect(screen.getByText("No git servers yet.")).toBeTruthy();
  const tip = button("About Servers");
  tip.focus();
  fireEvent.click(tip);
  expect(screen.getByText(TIPS.servers)).toBeTruthy();
  expect(document.activeElement).toBe(tip);
  expect(tip.closest(".mx-h")!.querySelector("h3")!.contains(tip)).toBe(false);
});

// Check.

const outcomes: [Partial<GitServerChecked>, string, string | null, string | null, string | null][] = [
  [{ outcome: "ok", message: "Works: signed in as a.sample, may clone and push." }, "ok", null, null, null],
  [
    { outcome: "token_refused", message: "GitLab refused the token: it expired or was revoked." },
    "bad",
    null,
    null,
    "✕ check failed: token refused",
  ],
  [
    { outcome: "scopes_missing", message: "The token lacks write_repository.", hint: "Agents can clone but not push with it." },
    "bad",
    null,
    "About the missing scope",
    "✕ check failed: a scope missing",
  ],
  [
    { outcome: "no_answer", message: "No answer in 5 seconds.", hint: "Check that LADO's computer reaches the server." },
    "warn",
    "Check again",
    "About no answer",
    "⚠ check: no answer",
  ],
  [
    { outcome: "cert_untrusted", message: "The server's certificate is not trusted.", hint: "Ask your IT department." },
    "bad",
    "Check again",
    "About the certificate",
    "✕ check failed: certificate not trusted",
  ],
  [
    { outcome: "redirect", message: "It redirects to https://sso.example/login: add that address instead." },
    "bad",
    null,
    null,
    "✕ check failed: redirect",
  ],
  [
    { outcome: "other_kind", message: "It answers as GitHub, not GitLab: remove it and add it again." },
    "bad",
    null,
    null,
    "✕ check failed: another kind",
  ],
];

test.each(outcomes)("Check shows %o as one line with its way out", async (found, tone, way, tip, closed) => {
  fake.servers = [CORP];
  fake.saved[CORP.host] = () => json(checked(CORP, found));
  await mount();
  openRow(CORP);
  press(`Check ${CORP.address}`);
  const line = await screen.findByText(found.message!, { exact: false });
  const result = line.closest(".gx-result") as HTMLElement;
  expect(result.className).toBe(`gx-result ${tone}${found.outcome === "ok" ? " works" : ""}`);
  const replace = button(`Replace the token of ${CORP.address}`);
  expect(replace.className).toBe(["token_refused", "scopes_missing"].includes(found.outcome!) ? "primary" : "quiet");
  expect(within(row(CORP)).getAllByRole("button", { name: `Replace the token of ${CORP.address}` })).toHaveLength(1);
  expect(result.getAttribute("role")).toBe(tone === "ok" ? "status" : "alert");
  expect(within(result).queryAllByRole("button").filter((b) => !b.classList.contains("info-tip")).map((b) => b.textContent)).toEqual(
    way ? [way] : [],
  );
  if (tip) {
    fireEvent.click(within(result).getByRole("button", { name: tip }));
    expect(within(result).getByText(found.hint!)).toBeTruthy();
  }
  await waitFor(() => expect(document.activeElement).toBe(button(`Check ${CORP.address}`)));
  openRow(CORP); // closed: line 2 follows the check
  expect(within(row(CORP)).getByText(closed ?? "signed in as a.sample")).toBeTruthy();
});

test("Checking… shows meanwhile with the button off; a server saved without a check gets its login", async () => {
  fake.servers = [GHE];
  let answer: (value: Response) => void = () => {};
  fake.saved[GHE.host] = () => new Promise<Response>((done) => (answer = done)) as unknown as Response;
  await mount();
  openRow(GHE);
  press(`Check ${GHE.address}`);
  expect(await screen.findByText("Checking…")).toBeTruthy();
  expect((button(`Check ${GHE.address}`) as HTMLButtonElement).disabled).toBe(true);
  const now = { ...GHE, login: "a.sample" };
  answer(json(checked(now, { outcome: "ok", message: "Works: GitHub, signed in as a.sample.", was_checked: false })));
  expect(await screen.findByText("Works: GitHub, signed in as a.sample.")).toBeTruthy();
  expect(screen.queryByText("Checking…")).toBeNull();
  expect(within(row(GHE)).getByText("a.sample", { selector: "b" })).toBeTruthy();
});

test("Check again checks again; a refused token's Replace token opens the form", async () => {
  fake.servers = [CORP];
  let n = 0;
  fake.saved[CORP.host] = () =>
    json(
      checked(CORP, ++n === 1 ? { outcome: "no_answer", message: "No answer in 5 seconds." } : { outcome: "token_refused", message: "GitLab refused the token: it expired or was revoked." }),
    );
  await mount();
  openRow(CORP);
  press(`Check ${CORP.address}`);
  await screen.findByText("⚠ No answer in 5 seconds.");
  press(`Check ${CORP.address} again`);
  await screen.findByText("GitLab refused the token: it expired or was revoked.");
  expect(n).toBe(2);
  expect(screen.queryByText("⚠ No answer in 5 seconds.")).toBeNull();
  expect(button(`Replace the token of ${CORP.address}`).className).toBe("primary");
  press(`Replace the token of ${CORP.address}`);
  expect(await screen.findByRole("textbox", { name: "New token" })).toBeTruthy();
});

// Replace token.

async function replaceWith(server: GitServerInfo, answer: (body: Record<string, unknown>) => Response) {
  fake.servers = [server];
  fake.add = answer;
  await mount();
  openRow(server);
  press(`Replace the token of ${server.address}`);
  const field = screen.getByRole("textbox", { name: "New token" });
  await waitFor(() => expect(document.activeElement).toBe(field));
  expect(button(`Replace the token of ${server.address}`).getAttribute("aria-pressed")).toBe("true");
  const link = within(row(server)).getByRole("link", { name: "its token page" });
  expect(link.getAttribute("href")).toBe(server.address + "/-/user_settings/personal_access_tokens");
  type(field, TOKEN);
  press("Save token");
  return field;
}

test("Replace token sends the saved address and the token, closes, says so, the focus on Replace token", async () => {
  let sent: Record<string, unknown> | undefined;
  await replaceWith(CORP, (body) => {
    sent = body;
    return json(added(CORP));
  });
  expect(await screen.findByText("Token replaced: signed in as a.sample.")).toBeTruthy();
  expect(sent).toEqual({ address: CORP.address, token: TOKEN, kind: null });
  expect(screen.queryByRole("textbox", { name: "New token" })).toBeNull();
  expect(document.body.innerHTML).not.toContain(TOKEN);
  await waitFor(() => expect(document.activeElement).toBe(button(`Replace the token of ${CORP.address}`)));
});

test("another user: the line says who it was before, with its tip", async () => {
  await replaceWith(CORP, () => json(added({ ...CORP, login: "b.sample" })));
  expect(await screen.findByText("Token replaced: signed in as b.sample.")).toBeTruthy();
  expect(screen.getByText("⚠ Before, it was a.sample.", { exact: false })).toBeTruthy();
  fireEvent.click(button("About the other user"));
  expect(screen.getByText(/now go as b\.sample/)).toBeTruthy();
});

test("a token without the push right is saved with a warning and Replace token", async () => {
  await replaceWith(CORP, () =>
    json(added(CORP, { warning: "The token lacks write_repository: agents can clone but not push.", missing_scopes: ["write_repository"] })),
  );
  const line = await screen.findByText("⚠ The token lacks write_repository: agents can clone but not push.");
  expect(line.closest(".gx-result")!.className).toBe("gx-result warn");
  expect(within(line.closest(".gx-result") as HTMLElement).queryByRole("button")).toBeNull();
  expect(within(row(CORP)).getAllByRole("button", { name: `Replace the token of ${CORP.address}` })).toHaveLength(1);
  expect(button(`Replace the token of ${CORP.address}`).className).toBe("primary");
});

test("a refused token stays, Save token off until it is edited", async () => {
  const field = await replaceWith(CORP, () => refused("GitLab refused this token: copy it whole or make a new one.", "token"));
  expect(await screen.findByText("GitLab refused this token: copy it whole or make a new one.")).toBeTruthy();
  expect((field as HTMLInputElement).value).toBe(TOKEN);
  expect((button("Save token") as HTMLButtonElement).disabled).toBe(true);
  type(field, TOKEN + "x");
  expect((button("Save token") as HTMLButtonElement).disabled).toBe(false);
});

test("no answer: nothing saved yet, then Save without a check under the saved kind", async () => {
  const sent: Record<string, unknown>[] = [];
  await replaceWith(CORP, (body) => {
    sent.push(body);
    return sent.length === 1
      ? refused("No answer in 5 seconds.", "address", true)
      : json(added({ ...CORP, login: null }));
  });
  expect(await screen.findByText("⚠ No answer in 5 seconds: save it without a check, as GitLab.")).toBeTruthy();
  press("Save without a check");
  expect(await screen.findByText("Saved without a check as GitLab.")).toBeTruthy();
  expect(sent.map((b) => b.kind)).toEqual([null, "gitlab"]);
  openRow(CORP);
  expect(within(row(CORP)).getByText("⚠ not checked")).toBeTruthy();
});

test("Esc cancels Replace token, the focus back on its button", async () => {
  fake.servers = [CORP];
  await mount();
  openRow(CORP);
  press(`Replace the token of ${CORP.address}`);
  const field = screen.getByRole("textbox", { name: "New token" });
  type(field, TOKEN);
  fireEvent.keyDown(field, { key: "Escape" });
  expect(screen.queryByRole("textbox", { name: "New token" })).toBeNull();
  await waitFor(() => expect(document.activeElement).toBe(button(`Replace the token of ${CORP.address}`)));
});

// The commit author.

test("Set author saves it, the focus on Edit", async () => {
  fake.servers = [GHE];
  await mount();
  openRow(GHE);
  press(`Set the commit author of ${GHE.address}`);
  type(screen.getByRole("textbox", { name: "Name" }), "Ivan Petrov");
  type(screen.getByRole("textbox", { name: "Email" }), "ivan.petrov@corp.example");
  press("Save author");
  expect(await screen.findByText("Author saved.")).toBeTruthy();
  expect(within(row(GHE)).getByText("Ivan Petrov <ivan.petrov@corp.example>")).toBeTruthy();
  await waitFor(() => expect(document.activeElement).toBe(button(`Edit the commit author of ${GHE.address}`)));
});

test("Remove clears the author at once with Undo; Undo sets it again, the focus on Edit", async () => {
  fake.servers = [CORP];
  await mount();
  openRow(CORP);
  press(`Remove the commit author of ${CORP.address}`);
  expect(await screen.findByText("Author removed.")).toBeTruthy();
  expect(within(row(CORP)).getByText("Your own git author")).toBeTruthy();
  const undo = button(`Undo the removal of the commit author of ${CORP.address}`);
  await waitFor(() => expect(document.activeElement).toBe(undo));
  fireEvent.click(undo);
  expect(await screen.findByText("Author saved.")).toBeTruthy();
  expect(fake.servers[0].author_name).toBe("Sample Name");
  expect(fake.calls.filter((c) => c.method === "PUT").map((c) => c.body)).toEqual([
    { name: "Sample Name", email: "sample.name@corp.example.com" },
  ]);
  await waitFor(() => expect(document.activeElement).toBe(button(`Edit the commit author of ${CORP.address}`)));
});

test("a wrong email shows under Email", async () => {
  fake.servers = [GHE];
  await mount();
  openRow(GHE);
  fake.author = () => refused("not an email address: name@host", "email");
  press(`Set the commit author of ${GHE.address}`);
  type(screen.getByRole("textbox", { name: "Name" }), "Ivan");
  type(screen.getByRole("textbox", { name: "Email" }), "ivan.petrov");
  press("Save author");
  const line = await screen.findByText("not an email address: name@host");
  expect(line.closest(".field")!.querySelector("input")).toBe(screen.getByRole("textbox", { name: "Email" }));
});

// Remove server.

test("Remove server asks in the foot, the focus on Cancel; done, its line and the focus on + Add server", async () => {
  fake.servers = [CORP, GHE];
  await mount();
  openRow(CORP);
  press(`Remove ${CORP.address}`);
  const ask = screen.getByRole("alertdialog");
  expect(within(ask).getByText(`Remove ${CORP.address}?`)).toBeTruthy();
  expect(within(ask).getByText("Its token and commit author go too. This cannot be undone.")).toBeTruthy();
  expect(document.activeElement).toBe(within(ask).getByRole("button", { name: "Cancel" }));
  fireEvent.click(within(ask).getByRole("button", { name: "Remove server" }));
  expect(await screen.findByText(`Removed ${CORP.address}.`)).toBeTruthy();
  await waitFor(() => expect(document.activeElement).toBe(button("Add server")));
});

test("a removal whose folder stays says so under its line", async () => {
  fake.servers = [CORP];
  fake.removal = "could not remove /home/x/.lado/git-servers: directory not empty";
  await mount();
  openRow(CORP);
  press(`Remove ${CORP.address}`);
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Remove server" }));
  expect(await screen.findByText(`Removed ${CORP.address}.`)).toBeTruthy();
  expect(screen.getByText("⚠ could not remove /home/x/.lado/git-servers: directory not empty")).toBeTruthy();
});

// One result at a time.

test("a check after a save leaves only the check's line", async () => {
  fake.servers = [CORP, GHE];
  fake.add = () => json(added(CORP));
  fake.saved[GHE.host] = () => json(checked(GHE, { outcome: "redirect", message: "It redirects to https://sso.example: add that address instead." }));
  await mount();
  openRow(CORP);
  openRow(GHE);
  press(`Replace the token of ${CORP.address}`);
  type(screen.getByRole("textbox", { name: "New token" }), TOKEN);
  press("Save token");
  await screen.findByText("Token replaced: signed in as a.sample.");
  openRow(CORP); // closing and opening a row is no action: its line stays
  openRow(CORP);
  expect(results().length).toBe(1);
  press(`Check ${GHE.address}`);
  await screen.findByText(/It redirects to/);
  expect(results().length).toBe(1);
  expect(screen.queryByText("Token replaced: signed in as a.sample.")).toBeNull();
});

// Add server.

const addressField = () => screen.getByRole("textbox", { name: "Address" }) as HTMLInputElement;
const tokenField = () => screen.getByRole("textbox", { name: "Token" }) as HTMLInputElement;
const addButton = () => screen.getByRole("button", { name: /^(Add server|Add without a check|Checking the token…)$/, hidden: false });
const formAdd = () => within(document.querySelector(".mx-form") as HTMLElement).getByRole("button", { name: /^(Add server|Add without a check|Checking the token…)$/ });

test("gitlab.com: GitLab answers, Token's link and scopes; the tips stand outside the labels", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  await mount();
  press("Add server");
  type(addressField(), "https://gitlab.com");
  expect(await screen.findByText("answers.", { exact: false })).toBeTruthy();
  const link = screen.getByRole("link", { name: "its token page" });
  expect(link.getAttribute("href")).toBe("https://gitlab.com/-/user_settings/personal_access_tokens");
  expect(link.parentElement!.textContent).toContain("read_repository, write_repository, read_api");
  const tip = button("About Address");
  expect(tip.closest("label")).toBeNull();
  tip.focus();
  fireEvent.click(tip);
  expect(document.activeElement).toBe(tip);
  expect(button("About Token").closest("label")).toBeNull();
});

test("Add fills in no server: Address empty and focused, its placeholder naming both kinds", async () => {
  fake.servers = [CORP];
  await mount();
  press("Add server");
  expect(addressField().value).toBe("");
  expect(addressField().placeholder).toBe("github.com or gitlab.example.com");
  await waitFor(() => expect(document.activeElement).toBe(addressField()));
  expect(screen.queryByText("answers.", { exact: false })).toBeNull();
});

test("plain http is warned first, with its tip, and Add stays possible", async () => {
  fake.checks["http://git.lab.example"] = { ...looksLike("http://git.lab.example", "gitlab"), warnings: ["the token goes to git.lab.example over plain http://"] };
  await mount();
  press("Add server");
  type(addressField(), "http://git.lab.example");
  expect(await screen.findByText("the token travels unencrypted.", { exact: false })).toBeTruthy();
  expect(button("About plain http")).toBeTruthy();
  type(tokenField(), TOKEN);
  expect((formAdd() as HTMLButtonElement).disabled).toBe(false);
});

test("an address already saved leads to its server's Replace token, the focus in New token", async () => {
  fake.servers = [CORP];
  fake.checks["gitlab.corp.example"] = { ...looksLike(CORP.address, "gitlab"), saved: true };
  await mount();
  press("Add server");
  type(addressField(), "gitlab.corp.example");
  expect(await screen.findByText("Already saved.")).toBeTruthy();
  expect((formAdd() as HTMLButtonElement).disabled).toBe(true);
  press("Replace its token");
  expect(screen.queryByRole("textbox", { name: "Address" })).toBeNull();
  const field = await screen.findByRole("textbox", { name: "New token" });
  await waitFor(() => expect(document.activeElement).toBe(field));
});

test("github.com is added as any server: GitHub answers, its token page with the scope repo", async () => {
  fake.checks["github.com"] = { ...looksLike("https://github.com", "github"), address: "https://github.com" };
  await mount();
  press("Add server");
  type(addressField(), "github.com");
  expect(await screen.findByText("answers.", { exact: false })).toBeTruthy();
  expect(screen.getByText("GitHub").tagName).toBe("B");
  const link = screen.getByRole("link", { name: "its token page" });
  expect(link.getAttribute("href")).toBe("https://github.com/settings/tokens");
  expect(link.parentElement!.textContent).toContain("scope repo");
  expect((formAdd() as HTMLButtonElement).disabled).toBe(true); // no token yet
});

test("github.com is a row like any other, with any server's panel", async () => {
  const dotcom: GitServerInfo = { ...GHE, address: "https://github.com", host: "github.com", login: "octo" };
  fake.servers = [dotcom, CORP];
  await mount();
  openRow(dotcom);
  expect(button(`Check ${dotcom.address}`)).toBeTruthy();
  expect(button(`Replace the token of ${dotcom.address}`)).toBeTruthy();
  expect(button(`Set the commit author of ${dotcom.address}`)).toBeTruthy();
  expect(button(`Remove ${dotcom.address}`).textContent).toBe("Remove server");
  expect(document.body.textContent).not.toMatch(/GH_TOKEN|not signed in|taken over/);
});

test("the Servers tip names GitHub and gh", () => {
  expect(TIPS.servers).toBe(
    "Your GitLab, gitlab.com, GitHub or GitHub Enterprise: agents clone and push there, and run gh, with the token you give. Running agents get a change after they restart.",
  );
});

test("no answer asks for the kind; Add without a check saves it as not checked", async () => {
  const at = "https://git.internal.example";
  fake.checks["git.internal.example"] = {
    ...nothing,
    address: at,
    choose_kind: true,
    unchecked: { message: "No answer in 5 seconds.", hint: "Choose its kind to save it without a check.", field: "address", warnings: [], choose_kind: true },
  };
  let sent: Record<string, unknown> | undefined;
  fake.add = (body) => {
    sent = body;
    const saved = { ...GHE, address: at, host: "git.internal.example", kind: "gitlab", kind_title: "GitLab" };
    fake.servers = [saved];
    return json(added(saved));
  };
  await mount();
  press("Add server");
  type(addressField(), "git.internal.example");
  expect(await screen.findByText("⚠ No answer in 5 seconds. Choose its kind to save it without a check.")).toBeTruthy();
  expect(button("About Kind")).toBeTruthy();
  type(tokenField(), TOKEN);
  expect((formAdd() as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("radio", { name: "GitLab" }));
  fireEvent.click(formAdd());
  expect(await screen.findByText("Saved without a check as GitLab.")).toBeTruthy();
  expect(sent).toEqual({ address: "git.internal.example", token: TOKEN, kind: "gitlab" });
  await waitFor(() => expect(document.activeElement).toBe(button(at)));
  expect(button(at).getAttribute("aria-expanded")).toBe("true");
});

test("a server that stops answering at Add offers Try again and the kind, the token kept", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  fake.add = () => refused("No answer in 5 seconds.", "address", true);
  await mount();
  press("Add server");
  type(addressField(), "https://gitlab.com");
  await screen.findByText("answers.", { exact: false });
  type(tokenField(), TOKEN);
  fireEvent.click(formAdd());
  expect(await screen.findByText("⚠ It stopped answering when you pressed Add.")).toBeTruthy();
  expect(button("Try again")).toBeTruthy();
  expect(screen.getByRole("radio", { name: "GitHub" })).toBeTruthy();
  expect(tokenField().value).toBe(TOKEN);
});

test("a refused token stays under Token; the done form opens the new row with its line", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  const com = { ...CORP, address: "https://gitlab.com", host: "gitlab.com", author_name: null, author_email: null };
  let n = 0;
  fake.add = () => {
    if (++n === 1) return refused("GitLab refused this token: copy it whole or make a new one.", "token");
    fake.servers = [com];
    return json(added(com, { warning: "The token lacks write_repository: agents can clone but not push.", missing_scopes: ["write_repository"] }));
  };
  await mount();
  press("Add server");
  type(addressField(), "https://gitlab.com");
  await screen.findByText("answers.", { exact: false });
  type(tokenField(), TOKEN);
  fireEvent.click(formAdd());
  const line = await screen.findByText("GitLab refused this token: copy it whole or make a new one.");
  expect(line.closest(".field")!.querySelector("input")).toBe(tokenField());
  expect((formAdd() as HTMLButtonElement).disabled).toBe(true);
  type(tokenField(), TOKEN + "x");
  fireEvent.click(formAdd());
  const warn = await screen.findByText("⚠ The token lacks write_repository: agents can clone but not push.");
  expect(warn.closest(".gx-top")).toBeTruthy();
  expect(document.body.innerHTML).not.toContain(TOKEN);
  await waitFor(() => expect(document.activeElement).toBe(button("https://gitlab.com")));
  // One Replace token: the warning at the panel's top has none, Sign-in's is the main one.
  expect(within(warn.closest(".gx-result") as HTMLElement).queryByRole("button")).toBeNull();
  expect(within(row(com)).getAllByRole("button", { name: "Replace the token of https://gitlab.com" })).toHaveLength(1);
  expect(button("Replace the token of https://gitlab.com").className).toBe("primary");
});

test("Author saved. keeps its ✓, a check's Works: has none", async () => {
  fake.servers = [CORP];
  await mount();
  openRow(CORP);
  press(`Remove the commit author of ${CORP.address}`);
  const done = await screen.findByText("Author removed.");
  expect(done.closest(".gx-result")!.className).toBe("gx-result ok");
});

test("Remove and Undo of the author are off while they ask; a second press sends nothing", async () => {
  fake.servers = [CORP];
  const removal = held();
  fake.authorHeld = removal.answer;
  await mount();
  openRow(CORP);
  const remove = button(`Remove the commit author of ${CORP.address}`) as HTMLButtonElement;
  const edit = button(`Edit the commit author of ${CORP.address}`) as HTMLButtonElement;
  fireEvent.click(remove);
  await waitFor(() => expect(remove.disabled).toBe(true));
  expect(edit.disabled).toBe(true);
  fireEvent.click(remove);
  expect(fake.calls.filter((c) => c.method === "DELETE")).toHaveLength(1);
  fake.authorHeld = null;
  removal.let_go(new Response());
  const undo = (await screen.findByRole("button", { name: `Undo the removal of the commit author of ${CORP.address}` })) as HTMLButtonElement;
  const set = button(`Set the commit author of ${CORP.address}`) as HTMLButtonElement;
  expect(set.disabled).toBe(false);
  const again = held();
  fake.authorHeld = again.answer;
  fireEvent.click(undo);
  await waitFor(() => expect(undo.disabled).toBe(true));
  expect(set.disabled).toBe(true);
  fireEvent.click(undo);
  expect(fake.calls.filter((c) => c.method === "PUT")).toHaveLength(1);
  fake.authorHeld = null;
  again.let_go(new Response());
  expect(await screen.findByText("Author saved.")).toBeTruthy();
});

test("Cancel closes Add, empties the token and gives the focus back to + Add server", async () => {
  await mount();
  press("Add server");
  const field = tokenField();
  type(field, TOKEN);
  press("Cancel");
  expect(field.value).toBe("");
  await waitFor(() => expect(document.activeElement).toBe(button("Add server")));
  expect(addButton).toBeTruthy();
});

test("one form at a time: a panel's form closes Add, Add closes a panel's form, the panel stays open", async () => {
  fake.servers = [CORP];
  await mount();
  press("Add server");
  openRow(CORP);
  press(`Replace the token of ${CORP.address}`);
  expect(screen.queryByRole("textbox", { name: "Address" })).toBeNull();
  expect(screen.getByRole("textbox", { name: "New token" })).toBeTruthy();
  press("Add server");
  expect(screen.queryByRole("textbox", { name: "New token" })).toBeNull();
  expect(addressField()).toBeTruthy();
  press(`Edit the commit author of ${CORP.address}`);
  expect(screen.queryByRole("textbox", { name: "Address" })).toBeNull();
  expect(button(CORP.address).getAttribute("aria-expanded")).toBe("true");
});

// Answers that come late, after another action.

// A fetch answer the test lets go when it says.
function held() {
  let let_go: (value: Response) => void = () => {};
  const answer = new Promise<Response>((done) => (let_go = done));
  return { answer: () => answer as unknown as Response, let_go };
}

test("two checks at once: each server keeps its own Checking… and its button off", async () => {
  fake.servers = [CORP, GHE];
  const a = held();
  const b = held();
  fake.saved[CORP.host] = a.answer;
  fake.saved[GHE.host] = b.answer;
  await mount();
  openRow(CORP);
  openRow(GHE);
  press(`Check ${CORP.address}`);
  press(`Check ${GHE.address}`);
  expect((button(`Check ${CORP.address}`) as HTMLButtonElement).disabled).toBe(true);
  expect((button(`Check ${GHE.address}`) as HTMLButtonElement).disabled).toBe(true);
  a.let_go(json(checked(CORP, { outcome: "ok", message: "Works: signed in as a.sample, may clone and push." })));
  await waitFor(() => expect((button(`Check ${CORP.address}`) as HTMLButtonElement).disabled).toBe(false));
  expect((button(`Check ${GHE.address}`) as HTMLButtonElement).disabled).toBe(true);
  expect(within(row(GHE)).getByText("Checking…")).toBeTruthy();
  expect(within(row(CORP)).queryByText("Checking…")).toBeNull();
  b.let_go(json(checked(GHE, { outcome: "redirect", message: "It redirects to https://sso.example: add that address instead." })));
  await screen.findByText(/It redirects to/);
  expect(results().length).toBe(1);
});

test("a check answered after the author's removal leaves its Undo and the focus alone", async () => {
  fake.servers = [CORP];
  const late = held();
  fake.saved[CORP.host] = late.answer;
  await mount();
  openRow(CORP);
  press(`Check ${CORP.address}`);
  press(`Remove the commit author of ${CORP.address}`);
  const undo = await screen.findByRole("button", { name: `Undo the removal of the commit author of ${CORP.address}` });
  await waitFor(() => expect(document.activeElement).toBe(undo));
  late.let_go(json(checked(CORP, { outcome: "ok", message: "Works: signed in as a.sample, may clone and push." })));
  await waitFor(() => expect((button(`Check ${CORP.address}`) as HTMLButtonElement).disabled).toBe(false));
  expect(screen.queryByText("Works: signed in as a.sample, may clone and push.")).toBeNull();
  expect(screen.getByText("Author removed.")).toBeTruthy();
  expect(document.activeElement).toBe(undo);
});

test("a check answered after its server's removal brings no row back", async () => {
  fake.servers = [CORP];
  const late = held();
  fake.saved[CORP.host] = late.answer;
  await mount();
  openRow(CORP);
  press(`Check ${CORP.address}`);
  press(`Remove ${CORP.address}`);
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Remove server" }));
  await screen.findByText(`Removed ${CORP.address}.`);
  late.let_go(json(checked(CORP, { outcome: "ok", message: "Works: signed in as a.sample, may clone and push." })));
  await new Promise((done) => setTimeout(done, 20));
  expect(screen.queryByRole("button", { name: CORP.address })).toBeNull();
  expect(screen.getByText(`Removed ${CORP.address}.`)).toBeTruthy();
});

test("Replace token cancelled while it saves: no line, no focus moved, the form stays closed", async () => {
  fake.servers = [CORP, GHE];
  const late = held();
  fake.add = late.answer;
  await mount();
  openRow(CORP);
  openRow(GHE);
  press(`Replace the token of ${CORP.address}`);
  type(screen.getByRole("textbox", { name: "New token" }), TOKEN);
  press("Save token");
  press("Cancel");
  press(`Set the commit author of ${GHE.address}`);
  const name = screen.getByRole("textbox", { name: "Name" });
  late.let_go(json(added(CORP)));
  await new Promise((done) => setTimeout(done, 20));
  expect(screen.queryByText("Token replaced: signed in as a.sample.")).toBeNull();
  expect(screen.getByRole("textbox", { name: "Name" })).toBe(name); // the other form stays open
});

test("Add cancelled while it saves: the server is listed, nothing else changes", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  const com = { ...CORP, address: "https://gitlab.com", host: "gitlab.com" };
  const late = held();
  fake.add = () => {
    fake.servers = [com];
    return late.answer();
  };
  await mount();
  press("Add server");
  type(addressField(), "https://gitlab.com");
  await screen.findByText("answers.", { exact: false });
  type(tokenField(), TOKEN);
  fireEvent.click(formAdd());
  press("Cancel");
  await waitFor(() => expect(document.activeElement).toBe(button("Add server")));
  late.let_go(json(added(com)));
  expect(await screen.findByRole("button", { name: "https://gitlab.com" })).toBeTruthy();
  expect(button("https://gitlab.com").getAttribute("aria-expanded")).toBe("false");
  expect(results().length).toBe(0);
  expect(document.activeElement).toBe(button("Add server"));
});

test("Replace token answered after a Check closes its form and leaves the check's line and focus", async () => {
  fake.servers = [CORP];
  const late = held();
  fake.add = late.answer;
  fake.saved[CORP.host] = () => json(checked(CORP, { outcome: "ok", message: "Works: signed in as a.sample, may clone and push." }));
  await mount();
  openRow(CORP);
  press(`Replace the token of ${CORP.address}`);
  type(screen.getByRole("textbox", { name: "New token" }), TOKEN);
  press("Save token");
  press(`Check ${CORP.address}`);
  await screen.findByText("Works: signed in as a.sample, may clone and push.");
  await waitFor(() => expect(document.activeElement).toBe(button(`Check ${CORP.address}`)));
  late.let_go(json(added(CORP)));
  await waitFor(() => expect(screen.queryByRole("textbox", { name: "New token" })).toBeNull());
  expect(screen.getByText("Works: signed in as a.sample, may clone and push.")).toBeTruthy();
  expect(screen.queryByText("Token replaced: signed in as a.sample.")).toBeNull();
  expect(document.activeElement).toBe(button(`Check ${CORP.address}`));
});

test("the author saved after a Check closes its form and leaves the check's line", async () => {
  fake.servers = [GHE];
  const late = held();
  fake.author = () => late.answer();
  fake.saved[GHE.host] = () => json(checked(GHE, { outcome: "unrecognised", message: "It answers as neither GitHub nor GitLab." }));
  await mount();
  openRow(GHE);
  press(`Set the commit author of ${GHE.address}`);
  type(screen.getByRole("textbox", { name: "Name" }), "Ivan");
  type(screen.getByRole("textbox", { name: "Email" }), "ivan@corp.example");
  press("Save author");
  press(`Check ${GHE.address}`);
  await screen.findByText("It answers as neither GitHub nor GitLab.");
  late.let_go(json({ server: { ...GHE, author_name: "Ivan", author_email: "ivan@corp.example" }, line: "" }));
  await waitFor(() => expect(screen.queryByRole("textbox", { name: "Name" })).toBeNull());
  expect(screen.getByText("It answers as neither GitHub nor GitLab.")).toBeTruthy();
  expect(screen.queryByText("Author saved.")).toBeNull();
});

test("Add answered after a Check closes the form, the server listed, the check's line kept", async () => {
  fake.servers = [GHE];
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  const com = { ...CORP, address: "https://gitlab.com", host: "gitlab.com" };
  const late = held();
  fake.add = () => {
    fake.servers = [GHE, com];
    return late.answer();
  };
  fake.saved[GHE.host] = () => json(checked(GHE, { outcome: "redirect", message: "It redirects to https://sso.example: add that address instead." }));
  await mount();
  openRow(GHE);
  press("Add server");
  type(addressField(), "https://gitlab.com");
  await screen.findByText("answers.", { exact: false });
  type(tokenField(), TOKEN);
  fireEvent.click(formAdd());
  press(`Check ${GHE.address}`);
  await screen.findByText(/It redirects to/);
  late.let_go(json(added(com)));
  await waitFor(() => expect(screen.queryByRole("textbox", { name: "Address" })).toBeNull());
  expect(button("https://gitlab.com")).toBeTruthy();
  expect(screen.getByText(/It redirects to/)).toBeTruthy();
  expect(results().length).toBe(1);
});

test("an Add cancelled and opened again is not closed by the first one's late answer", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  const com = { ...CORP, address: "https://gitlab.com", host: "gitlab.com" };
  const late = held();
  fake.add = () => late.answer();
  await mount();
  press("Add server");
  type(addressField(), "https://gitlab.com");
  await screen.findByText("answers.", { exact: false });
  type(tokenField(), TOKEN);
  fireEvent.click(formAdd());
  press("Cancel");
  press("Add server");
  const again = addressField();
  late.let_go(json(added(com)));
  await new Promise((done) => setTimeout(done, 20));
  expect(addressField()).toBe(again);
});

test("an address saved as http:// or under a path leads to its server all the same", async () => {
  const lab = { ...GHE, address: "http://git.lab.example", host: "git.lab.example" };
  fake.servers = [lab];
  fake.checks["git.lab.example"] = { ...looksLike("https://git.lab.example", "gitlab"), saved: true };
  await mount();
  press("Add server");
  type(addressField(), "git.lab.example");
  expect(await screen.findByText("Already saved.")).toBeTruthy();
  press("Replace its token");
  expect(await screen.findByRole("textbox", { name: "New token" })).toBeTruthy();
});

test("Try again whose token is refused drops the stopped-answering line and the kind", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  let n = 0;
  fake.add = () =>
    ++n === 1
      ? refused("No answer in 5 seconds.", "address", true)
      : refused("GitLab refused this token: copy it whole or make a new one.", "token");
  await mount();
  press("Add server");
  type(addressField(), "https://gitlab.com");
  await screen.findByText("answers.", { exact: false });
  type(tokenField(), TOKEN);
  fireEvent.click(formAdd());
  await screen.findByText("⚠ It stopped answering when you pressed Add.");
  press("Try again");
  await screen.findByText("GitLab refused this token: copy it whole or make a new one.");
  expect(screen.queryByText("⚠ It stopped answering when you pressed Add.")).toBeNull();
  expect(screen.queryByRole("radio")).toBeNull();
  expect(formAdd().textContent).toBe("Add server");
});

test("a check of a server removed elsewhere says so in its place", async () => {
  fake.servers = [CORP];
  fake.saved[CORP.host] = () => {
    fake.servers = [];
    return json({ detail: { message: "gitlab.corp.example is no saved git server", hint: "", field: "address", warnings: [], choose_kind: false } }, 404);
  };
  await mount();
  openRow(CORP);
  press(`Check ${CORP.address}`);
  expect(await screen.findByText("gitlab.corp.example is no saved git server")).toBeTruthy();
  await waitFor(() => expect(screen.queryByRole("button", { name: CORP.address })).toBeNull());
  expect(screen.getByText("gitlab.corp.example is no saved git server")).toBeTruthy();
});

test("Replace token with no answer says the server's own reason", async () => {
  await replaceWith(CORP, () => refused("No answer: the name is not found.", "address", true));
  expect(await screen.findByText("⚠ No answer: the name is not found: save it without a check, as GitLab.")).toBeTruthy();
});

// The page's address: ?check=<host>, ?add=<address> (a clone's note opens them).

function Where() {
  const at = useLocation();
  return <output aria-label="Where">{at.pathname + at.search}</output>;
}

async function mountAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <GitServersPage />
      <Where />
    </MemoryRouter>,
  );
  await screen.findByRole("button", { name: "About Servers" });
}

const where = () => screen.getByRole("status", { name: "Where" }).textContent;

test("?check= opens that server's panel and checks it once; the query leaves", async () => {
  fake.servers = [CORP, GHE];
  const late = held();
  fake.saved[CORP.host] = late.answer;
  await mountAt(`/settings/git-servers?check=${encodeURIComponent(CORP.host)}`);
  expect(await within(row(CORP)).findByText("Checking…")).toBeTruthy();
  expect(button(CORP.address).getAttribute("aria-expanded")).toBe("true");
  expect(button(GHE.address).getAttribute("aria-expanded")).toBe("false");
  await waitFor(() => expect(where()).toBe("/settings/git-servers"));
  late.let_go(json(checked(CORP, { outcome: "token_refused", message: "GitLab refused the token: it expired or was revoked." })));
  expect(await screen.findByText("GitLab refused the token: it expired or was revoked.")).toBeTruthy();
  await new Promise((done) => setTimeout(done, 20));
  expect(fake.calls.filter((c) => c.method === "POST" && c.path.endsWith("/check"))).toHaveLength(1);
});

test("?add= opens Add with the address, checked as typed, the focus in Token; the query leaves", async () => {
  const at = "https://git.acme.example";
  fake.checks[at] = looksLike(at, "gitlab");
  await mountAt(`/settings/git-servers?add=${encodeURIComponent(at)}`);
  expect((await screen.findByRole("textbox", { name: "Address" }) as HTMLInputElement).value).toBe(at);
  await waitFor(() => expect(document.activeElement).toBe(tokenField()));
  await screen.findByText("answers.", { exact: false });
  expect(fake.calls.some((c) => c.path === "/api/git-servers/check" && c.body?.address === at)).toBe(true);
  await waitFor(() => expect(where()).toBe("/settings/git-servers"));
});

test("?check= of a host no server is saved for opens nothing; the query leaves", async () => {
  fake.servers = [CORP];
  await mountAt("/settings/git-servers?check=git.acme.example");
  await waitFor(() => expect(where()).toBe("/settings/git-servers"));
  expect(button(CORP.address).getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("textbox", { name: "Address" })).toBeNull();
  expect(fake.calls.filter((c) => c.method === "POST")).toEqual([]);
});
