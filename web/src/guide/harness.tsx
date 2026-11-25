// The guide's tests' page: the shell's and Settings' elements the guide points at, by their
// markers, without the real pages and their requests; Guide over them.
import { act, render } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { Link, MemoryRouter, Route, Routes } from "react-router";
import { vi } from "vitest";

import type { GuideInfo } from "../api";
import { publish, resetFacts } from "./facts";
import Guide from "./Guide";

export const INFO: GuideInfo = {
  auto: true,
  completed: false,
  shown: [],
  tips_off: false,
  telemetry_asked: false,
  facts: { model: false, author: false },
};

export type Call = { method: string; path: string; body: Record<string, unknown> | undefined };

// The server of the guide: each POST answers the record as the action changed it.
export function serveGuide(start: GuideInfo = INFO) {
  const calls: Call[] = [];
  let now = { ...start };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, path, body });
      if (method === "POST" && body) {
        if (body.action === "shown") now = { ...now, shown: [...new Set([...now.shown, ...body.ids])] };
        if (body.action === "complete") now = { ...now, completed: true, facts: null };
        if (body.action === "tips_off") now = { ...now, tips_off: true };
      }
      return new Response(JSON.stringify(now));
    }),
  );
  return {
    calls,
    posts: () => calls.filter((c) => c.method === "POST").map((c) => c.body),
  };
}

export function Rail({ drawer = false }: { drawer?: boolean }) {
  return (
    <nav className="rail" data-open={drawer || undefined}>
      <Link to="/" className="rail-link">
        Home
      </Link>
      <Link to="/settings/general" className="rail-link" data-guide="rail-settings">
        Settings
      </Link>
      <button type="button" className="rail-link" data-guide="rail-new-session" onClick={() => launchOpen?.(true)}>
        New session
      </button>
    </nav>
  );
}

let launchOpen: ((open: boolean) => void) | null = null;

function Launch() {
  const [open, setOpen] = useState(false);
  launchOpen = setOpen;
  if (!open) return null;
  return (
    <dialog open aria-label="New session">
      <div className="field launch-task" data-guide="launch-task">
        <label htmlFor="task">Task</label>
        <textarea id="task" />
      </div>
    </dialog>
  );
}

function SettingsList() {
  return (
    <nav className="snav">
      <Link to="/settings/general">General</Link>
      <Link to="/settings/agent-clis" data-guide="agent-clis-link">
        Agent CLIs
      </Link>
      <Link to="/settings/model-servers" data-guide="model-servers-link">
        Model servers
      </Link>
      <Link to="/settings/git-servers" data-guide="git-servers-link">
        Git servers
      </Link>
    </nav>
  );
}

export function Settings({ children }: { children?: ReactNode }) {
  return (
    <main>
      <SettingsList />
      <section>
        <h2>Settings</h2>
        {children}
      </section>
    </main>
  );
}

function AgentClis({ rows }: { rows: string[] }) {
  return (
    <Settings>
      <ul>
        {rows.map((name) => (
          <li key={name} data-guide={`cli-row-${name}`}>
            {name} <button type="button">Log in…</button>
          </li>
        ))}
      </ul>
    </Settings>
  );
}

export type Page = { path: string; element: ReactNode };

// The guide over the rail, Settings and New session; `pages` add or replace routes.
export function showGuide(
  path: string,
  info: GuideInfo = INFO,
  options: { pages?: Page[]; rows?: string[]; restarted?: boolean } = {},
) {
  resetFacts();
  const server = serveGuide(info);
  const replaced = new Set((options.pages ?? []).map((page) => page.path));
  const base = (path: string, element: ReactNode) =>
    replaced.has(path) ? null : <Route path={path} element={element} />;
  function Root() {
    const [now, setNow] = useState(info);
    return (
      <>
        <Rail />
        <Routes>
          {base("/", <main><h2>Home</h2></main>)}
          {base("/settings/general", <Settings />)}
          {base("/settings/agent-clis", <AgentClis rows={options.rows ?? ["claude", "codex"]} />)}
          {base(
            "/settings/model-servers",
            <Settings>
              <button type="button" data-guide="model-server-add">
                Add server
              </button>
            </Settings>,
          )}
          {base(
            "/settings/git-servers",
            <Settings>
              <ul>
                <li data-guide="author-row">
                  LADO's author <button type="button">Set author</button>
                </li>
              </ul>
            </Settings>,
          )}
          {(options.pages ?? []).map((page) => (
            <Route key={page.path} path={page.path} element={page.element} />
          ))}
        </Routes>
        <Launch />
        <Guide info={now} restarted={options.restarted ?? false} onInfo={setNow} />
      </>
    );
  }
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <Root />
    </MemoryRouter>,
  );
  return { ...view, ...server };
}

// What a Settings page publishes, as the real pages do (facts.ts).
export function publishLogins(rows: { name: string; installed?: boolean; loggedIn?: boolean }[], checking = false) {
  act(() =>
    publish("logins", {
      checking,
      rows: rows.map((r) => ({ name: r.name, ready: true, installed: r.installed ?? true, loggedIn: r.loggedIn ?? false })),
    }),
  );
}

export const card = () => document.querySelector<HTMLElement>(".gd-card");
export const cardTitle = () => card()?.querySelector("h2")?.textContent ?? null;
