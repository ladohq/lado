import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { GitServerCheck, GitServerInfo, GitServers } from "./api";
import { GIT_LEAD, GitServersPage } from "./GitServers";

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
const GITLAB_COM: GitServerInfo = {
  address: "https://gitlab.com",
  host: "gitlab.com",
  kind: "gitlab",
  kind_title: "GitLab",
  login: "alex",
  has_token: true,
  author_name: null,
  author_email: null,
};
const CORP: GitServerInfo = {
  address: "https://git.corp.example",
  host: "git.corp.example",
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

type Call = { method: string; path: string; body: Record<string, unknown> | undefined };

class Fake {
  servers: GitServerInfo[] = [];
  calls: Call[] = [];
  checks: Record<string, GitServerCheck | (() => Promise<Response>)> = {};
  add: (body: Record<string, unknown>) => Response = () => new Response("{}", { status: 500 });
  authorRefusal: Response | null = null;
  author(method: string, path: string, body: Record<string, unknown> | undefined): Response {
    if (this.authorRefusal) return this.authorRefusal;
    const host = decodeURIComponent(path.slice("/api/git-servers/".length, -"/author".length));
    const server = this.servers.find((s) => s.host === host)!;
    const set = method === "PUT";
    const saved = {
      ...server,
      author_name: set ? String(body!.name).trim() : null,
      author_email: set ? String(body!.email).trim() : null,
    };
    this.servers = this.servers.map((s) => (s.host === host ? saved : s));
    const line = set
      ? `Agents commit to ${server.address} as ${saved.author_name} <${saved.author_email}>.`
      : `Agents commit to ${server.address} with your own git author again.`;
    return new Response(JSON.stringify({ server: saved, line }), { status: 200 });
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
        if (path === "/api/git-servers/check") {
          const found = this.checks[(body as { address: string }).address] ?? nothing;
          return typeof found === "function" ? found() : json(found);
        }
        if (path === "/api/git-servers" && method === "POST") return this.add(body!);
        if (path.endsWith("/author")) return this.author(method, path, body);
        if (path.startsWith("/api/git-servers/") && method === "DELETE") {
          const host = decodeURIComponent(path.slice("/api/git-servers/".length));
          this.servers = this.servers.filter((s) => s.host !== host);
          return json(listing());
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
  await screen.findByText(GIT_LEAD);
}

const addressField = () => screen.getByRole("textbox", { name: "Address" }) as HTMLInputElement;
const tokenField = () => screen.getByRole("textbox", { name: "Token" }) as HTMLInputElement;
const addButton = () => screen.getByRole("button", { name: /^(Add server|Add without a check|checking the server…)$/ });
// + Add server: its "+" is not read out.
const plusAdd = () => screen.getByRole("button", { name: "Add server" });
const openForm = () => fireEvent.click(plusAdd());
const type = (field: HTMLInputElement, value: string) => fireEvent.change(field, { target: { value } });
const refused = (message: string, field: string, hint = "") =>
  new Response(JSON.stringify({ detail: { message, hint, field, warnings: [] } }), { status: 400 });

test("the list says each server's kind and login or why it is not trusted", async () => {
  fake.servers = [GITLAB_COM, CORP, { ...CORP, address: "https://g.lan", host: "g.lan", has_token: false }];
  await mount();
  expect(screen.getByRole("heading", { name: "Servers 3" })).toBeTruthy();
  const rows = screen.getAllByRole("listitem").filter((li) => li.querySelector(".mx-head"));
  expect(rows.map((li) => li.querySelector(".mx-head")!.textContent)).toEqual([
    "https://gitlab.comGitLabsigned in as alex",
    "https://git.corp.exampleGitHub⚠ not checked: saved without a check",
    "https://g.lanGitHub⚠ its token file is missing: add it again",
  ]);
  expect(screen.getByRole("button", { name: "Remove https://gitlab.com" })).toBeTruthy();
  expect(fake.calls.filter((c) => c.path !== "/api/git-servers")).toEqual([]); // asks no server
});

test("with none saved: no count, the lead and the button only", async () => {
  await mount();
  expect(screen.getByRole("heading", { name: "Servers" })).toBeTruthy();
  expect(plusAdd().textContent).toBe("+ Add server");
});

test("Add server starts with gitlab.com selected and its hint and token link", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  await mount();
  openForm();
  const field = addressField();
  expect(field.value).toBe("https://gitlab.com");
  expect(document.activeElement).toBe(field);
  expect([field.selectionStart, field.selectionEnd]).toEqual([0, field.value.length]);
  expect(screen.getByText("checking https://gitlab.com …")).toBeTruthy();
  await screen.findByText("Looks like GitLab; the token tells for sure.");
  const link = screen.getByRole("link", { name: "https://gitlab.com/-/user_settings/personal_access_tokens" });
  expect(link.closest(".field-note")!.textContent).toBe(
    "Make one at https://gitlab.com/-/user_settings/personal_access_tokens with the scopes read_repository, write_repository, read_api.",
  );
  expect(fake.calls.find((c) => c.path === "/api/git-servers/check")!.body).toEqual({ address: "https://gitlab.com" });
  expect((addButton() as HTMLButtonElement).disabled).toBe(true); // no token yet
});

test("with gitlab.com saved Address starts empty", async () => {
  fake.servers = [GITLAB_COM];
  await mount();
  openForm();
  expect(addressField().value).toBe("");
  expect(document.activeElement).toBe(addressField());
});

test("Add sends the token once, empties it, and the saved row takes the form's place", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  fake.add = (body) => {
    fake.servers = [GITLAB_COM];
    expect(body).toEqual({ address: "https://gitlab.com", token: TOKEN, kind: null });
    return new Response(
      JSON.stringify({
        server: GITLAB_COM,
        line: "Saved git server https://gitlab.com: GitLab, signed in as alex.",
        replaced: false,
        warnings: [],
      }),
    );
  };
  await mount();
  openForm();
  await screen.findByText("Looks like GitLab; the token tells for sure.");
  type(tokenField(), TOKEN);
  fireEvent.click(addButton());
  await screen.findByText("Saved git server https://gitlab.com: GitLab, signed in as alex.");
  expect(screen.getByText("Agents started from now on reach it; restart running agents to give it to them.")).toBeTruthy();
  expect(screen.queryByRole("textbox", { name: "Token" })).toBeNull();
  expect(document.body.innerHTML).not.toContain(TOKEN);
  await waitFor(() => expect(document.activeElement?.textContent).toContain("signed in as alex"));
  expect(fake.calls.filter((c) => JSON.stringify(c.body ?? "").includes(TOKEN)).map((c) => c.path)).toEqual([
    "/api/git-servers",
  ]);
});

test("a refused token stays under Token, Add off until it is edited", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  fake.add = () =>
    refused(
      "GitLab at https://gitlab.com refuses the token",
      "token",
      "make a token at https://gitlab.com/-/user_settings/personal_access_tokens (scopes read_repository, write_repository, read_api)",
    );
  await mount();
  openForm();
  await screen.findByText("Looks like GitLab; the token tells for sure.");
  type(tokenField(), TOKEN);
  fireEvent.click(addButton());
  const line = await screen.findByText("GitLab at https://gitlab.com refuses the token");
  expect(line.closest(".field")!.querySelector("input")).toBe(tokenField());
  expect(tokenField().value).toBe(TOKEN);
  expect((addButton() as HTMLButtonElement).disabled).toBe(true);
  type(tokenField(), TOKEN + "x");
  expect(screen.queryByText("GitLab at https://gitlab.com refuses the token")).toBeNull();
  expect((addButton() as HTMLButtonElement).disabled).toBe(false);
});

test("a refusal of another field empties the token", async () => {
  fake.checks["https://gitlab.com"] = looksLike("https://gitlab.com", "gitlab");
  fake.add = () => refused("gitlab.com already has a git server, https://gitlab.com:8443", "address");
  await mount();
  openForm();
  await screen.findByText("Looks like GitLab; the token tells for sure.");
  type(tokenField(), TOKEN);
  fireEvent.click(addButton());
  const line = await screen.findByText(/already has a git server/);
  expect(line.closest(".field")!.querySelector("input")).toBe(addressField());
  expect(tokenField().value).toBe("");
});

test("Cancel and the closing form empty the token", async () => {
  await mount();
  openForm();
  const field = tokenField();
  type(field, TOKEN);
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(field.value).toBe("");
  expect(document.body.innerHTML).not.toContain(TOKEN);
});

test("a server that does not answer asks for the kind; Add without a check sends it", async () => {
  const at = "https://git.internal.example";
  fake.checks["git.internal.example"] = {
    ...nothing,
    address: at,
    choose_kind: true,
    unchecked: {
      message: "git.internal.example does not answer: it did not answer in 5 s",
      hint: "If the server is there for git but its API is not reachable from here, choose its kind to save it without a check.",
      field: "address",
      warnings: [],
    },
  };
  let sent: Record<string, unknown> | undefined;
  fake.add = (body) => {
    sent = body;
    return refused("stop here", "");
  };
  await mount();
  openForm();
  type(addressField(), "git.internal.example");
  await screen.findByText("⚠ git.internal.example does not answer: it did not answer in 5 s", { exact: false });
  expect(screen.queryByText(/Make one at/)).toBeNull();
  type(tokenField(), TOKEN);
  const add = addButton() as HTMLButtonElement;
  expect(add.textContent).toBe("Add without a check");
  expect(add.disabled).toBe(true);
  fireEvent.click(screen.getByRole("radio", { name: "GitLab" }));
  expect(add.disabled).toBe(false);
  expect(screen.getByRole("link").getAttribute("href")).toBe(`${at}/-/user_settings/personal_access_tokens`);
  fireEvent.click(add);
  await screen.findByText("stop here");
  expect(sent).toEqual({ address: "git.internal.example", token: TOKEN, kind: "gitlab" });
});

test("a hint never goes to Add as a kind, and a redirect shows no kind choice", async () => {
  fake.checks["git.sso.example"] = {
    ...nothing,
    address: "https://git.sso.example",
    refusals: [
      {
        message: "https://git.sso.example sends to https://sso.example/login; give the server's own address",
        hint: "",
        field: "address",
        warnings: [],
      },
    ],
  };
  await mount();
  openForm();
  type(addressField(), "git.sso.example");
  await screen.findByText(/sends to https:\/\/sso.example\/login/);
  expect(screen.queryByRole("radio")).toBeNull();
  type(tokenField(), TOKEN);
  expect((addButton() as HTMLButtonElement).disabled).toBe(true);
});

test("a late answer of an address no longer typed is dropped", async () => {
  let answerFirst: (r: Response) => void = () => undefined;
  fake.checks["first.example"] = () => new Promise<Response>((resolve) => (answerFirst = resolve));
  fake.checks["second.example"] = looksLike("https://second.example", "github");
  await mount();
  openForm();
  type(addressField(), "first.example");
  await waitFor(() => expect(fake.calls.some((c) => c.body?.address === "first.example")).toBe(true));
  type(addressField(), "second.example");
  await screen.findByText("Looks like GitHub; the token tells for sure.");
  await act(async () => answerFirst(new Response(JSON.stringify(looksLike("https://first.example", "gitlab")))));
  expect(screen.queryByText("Looks like GitLab; the token tells for sure.")).toBeNull();
  expect(screen.getByRole("link").getAttribute("href")).toBe("https://second.example/settings/tokens");
});

test("github.com is refused under Address and the plain-http warning shows", async () => {
  fake.checks["github.com"] = {
    ...nothing,
    address: "https://github.com",
    refusals: [
      {
        message: "github.com is reached through gh's login (GH_TOKEN or gh auth login); LADO keeps no token for it",
        hint: "",
        field: "address",
        warnings: [],
      },
    ],
  };
  fake.checks["http://git.lab.example"] = {
    ...looksLike("http://git.lab.example", "gitlab"),
    warnings: ["the token goes to git.lab.example over plain http://, unencrypted; use https:// if the server has it"],
  };
  await mount();
  openForm();
  type(addressField(), "github.com");
  await screen.findByText(/reached through gh's login/);
  type(addressField(), "http://git.lab.example");
  await screen.findByText(/over plain http:\/\/, unencrypted/);
  type(tokenField(), TOKEN);
  expect((addButton() as HTMLButtonElement).disabled).toBe(false);
});

test("Remove asks first, then leaves its line and the focus on + Add server", async () => {
  fake.servers = [GITLAB_COM, CORP];
  await mount();
  fireEvent.click(screen.getByRole("button", { name: "Remove https://git.corp.example" }));
  const ask = screen.getByRole("alertdialog");
  expect(ask.textContent).toContain(
    "Remove https://git.corp.example? Its token is deleted too. This cannot be undone. Running agents keep reaching it until they restart.",
  );
  expect(document.activeElement).toBe(within(ask).getByRole("button", { name: "Cancel" }));
  fireEvent.keyDown(ask, { key: "Escape" });
  expect(screen.queryByRole("alertdialog")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Remove https://git.corp.example" }));
  fireEvent.click(screen.getByRole("button", { name: "Remove server" }));
  await screen.findByText("Removed https://git.corp.example.");
  expect(fake.calls.at(-1)).toMatchObject({ method: "DELETE", path: "/api/git-servers/git.corp.example" });
  await waitFor(() => expect(document.activeElement).toBe(plusAdd()));
  expect(screen.getByRole("heading", { name: "Servers 1" })).toBeTruthy();
});

// The commit author.

const AUTHORED: GitServerInfo = { ...CORP, author_name: "Ivan Petrov", author_email: "ivan@corp.example" };
const pencil = (address: string) => screen.getByRole("button", { name: `Commit author of ${address}` });
const nameField = () => screen.getByRole("textbox", { name: "Name" }) as HTMLInputElement;
const emailField = () => screen.getByRole("textbox", { name: "Email" }) as HTMLInputElement;
const saveAuthor = () => screen.getByRole("button", { name: "Save author" }) as HTMLButtonElement;
const AUTHOR_NOTE = "Agents' commits to this server's repositories carry this name and email; elsewhere your own git author.";
const AUTHOR_RESTART = "Agents started from now on commit so; restart running agents to give it to them.";

test("a row with an author says whom agents commit as; one without says nothing of it", async () => {
  fake.servers = [GITLAB_COM, AUTHORED];
  await mount();
  expect(screen.getByText("commits as Ivan Petrov <ivan@corp.example>")).toBeTruthy();
  expect(screen.getAllByText(/^commits as/)).toHaveLength(1);
  expect(pencil("https://gitlab.com").getAttribute("title")).toBe("Commit author");
});

test("✎ opens the form with the saved author, the focus on Name; Esc cancels", async () => {
  fake.servers = [AUTHORED];
  await mount();
  fireEvent.click(pencil(AUTHORED.address));
  expect(pencil(AUTHORED.address).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText(AUTHOR_NOTE)).toBeTruthy();
  expect(nameField().value).toBe("Ivan Petrov");
  expect(emailField().value).toBe("ivan@corp.example");
  expect(document.activeElement).toBe(nameField());
  expect(saveAuthor().disabled).toBe(true); // nothing changed
  expect(screen.getByRole("button", { name: "Remove author" })).toBeTruthy();
  fireEvent.keyDown(nameField(), { key: "Escape" });
  expect(screen.queryByRole("textbox", { name: "Name" })).toBeNull();
});

test("Save author is on once both are filled; no Remove author without one", async () => {
  fake.servers = [GITLAB_COM];
  await mount();
  fireEvent.click(pencil(GITLAB_COM.address));
  expect(nameField().value).toBe("");
  expect(screen.queryByRole("button", { name: "Remove author" })).toBeNull();
  expect(saveAuthor().disabled).toBe(true);
  type(nameField(), "Alex");
  expect(saveAuthor().disabled).toBe(true);
  type(emailField(), "  ");
  expect(saveAuthor().disabled).toBe(true);
  type(emailField(), "alex@home.example");
  expect(saveAuthor().disabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("textbox", { name: "Name" })).toBeNull();
});

test("✎ and 🗑 share the place under the row: one opens, the other closes", async () => {
  fake.servers = [GITLAB_COM];
  await mount();
  fireEvent.click(pencil(GITLAB_COM.address));
  fireEvent.click(screen.getByRole("button", { name: "Remove https://gitlab.com" }));
  expect(screen.getByRole("alertdialog")).toBeTruthy();
  expect(screen.queryByRole("textbox", { name: "Name" })).toBeNull();
  fireEvent.click(pencil(GITLAB_COM.address));
  expect(screen.queryByRole("alertdialog")).toBeNull();
  expect(nameField()).toBeTruthy();
});

test("Save author sets it, says so above the row and puts the focus on the row", async () => {
  fake.servers = [GITLAB_COM];
  await mount();
  fireEvent.click(pencil(GITLAB_COM.address));
  type(nameField(), "Alex Smith");
  type(emailField(), "alex@home.example");
  fireEvent.click(saveAuthor());
  await screen.findByText("Agents commit to https://gitlab.com as Alex Smith <alex@home.example>.");
  expect(fake.calls.at(-2)).toMatchObject({
    method: "PUT",
    path: "/api/git-servers/gitlab.com/author",
    body: { name: "Alex Smith", email: "alex@home.example" },
  });
  expect(screen.getByText(AUTHOR_RESTART)).toBeTruthy();
  expect(screen.queryByRole("textbox", { name: "Name" })).toBeNull();
  await screen.findByText("commits as Alex Smith <alex@home.example>");
  await waitFor(() => expect(document.activeElement?.textContent).toContain("https://gitlab.com"));
  fireEvent.click(plusAdd()); // the next change on the page: the lines go
  expect(screen.queryByText(AUTHOR_RESTART)).toBeNull();
});

test("a refusal stands under its field; one of no field under the buttons", async () => {
  fake.servers = [GITLAB_COM];
  await mount();
  fireEvent.click(pencil(GITLAB_COM.address));
  type(nameField(), "Alex");
  type(emailField(), "alex");
  fake.authorRefusal = refused("not an email address: name@host", "email");
  fireEvent.click(saveAuthor());
  await screen.findByText("not an email address: name@host");
  expect(emailField().getAttribute("aria-invalid")).toBe("true");
  expect(nameField().getAttribute("aria-invalid")).toBeNull();
  type(emailField(), "alex@x");
  expect(screen.queryByText("not an email address: name@host")).toBeNull();
  const old = "git 2.34.1 is older than 2.36, which a commit author of a git server needs; update git";
  fake.authorRefusal = refused(old, "");
  fireEvent.click(saveAuthor());
  const note = await screen.findByText(old);
  expect(note.closest(".mx-form-acts")).toBeTruthy();
});

test("Remove author clears it with no question and says so", async () => {
  fake.servers = [AUTHORED];
  await mount();
  fireEvent.click(pencil(AUTHORED.address));
  fireEvent.click(screen.getByRole("button", { name: "Remove author" }));
  await screen.findByText("Agents commit to https://git.corp.example with your own git author again.");
  expect(fake.calls.some((c) => c.method === "DELETE" && c.path === "/api/git-servers/git.corp.example/author")).toBe(
    true,
  );
  await waitFor(() => expect(screen.queryByText(/^commits as/)).toBeNull());
  expect(screen.queryByRole("textbox", { name: "Name" })).toBeNull();
});
