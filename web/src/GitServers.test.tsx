// Settings → Git servers (GitServers.tsx) against a fake API: the rows and panels, Check and
// its lines, Replace token, the commit author with Undo, Remove server, Add's states, one
// result line at a time and where the focus goes.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
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
        if (path.endsWith("/author")) return this.author(method, path, body);
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
    "Replace token",
    null,
    "✕ check failed: token refused",
  ],
  [
    { outcome: "scopes_missing", message: "The token lacks write_repository.", hint: "Agents can clone but not push with it." },
    "bad",
    "Replace token",
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
  expect(result.className).toBe(`gx-result ${tone}`);
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
  fireEvent.click(within(document.querySelector(".gx-result") as HTMLElement).getByRole("button", { name: `Replace the token of ${CORP.address}` }));
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
  expect(within(line.closest(".gx-result") as HTMLElement).getByRole("button").textContent).toBe("Replace token");
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
  expect(addressField().value).toBe("https://gitlab.com");
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

test("github.com is refused under Address, Add off", async () => {
  fake.checks["github.com"] = {
    ...nothing,
    refusals: [{ message: "github.com uses the GitHub CLI's login: it is not added here.", hint: "", field: "address", warnings: [], choose_kind: false }],
  };
  await mount();
  press("Add server");
  type(addressField(), "github.com");
  expect(await screen.findByText("github.com uses the GitHub CLI's login: it is not added here.")).toBeTruthy();
  expect((formAdd() as HTMLButtonElement).disabled).toBe(true);
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
