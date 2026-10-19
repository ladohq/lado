// Forget stopped sessions (docs/design/ui.md, Launch and session control): the window the
// Stopped band opens, its ticks, the open runs' switch, and the forgets one at a time
// through the single Forget's API, each reported.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { SessionInfo } from "./api";
import { ForgetManyDialog } from "./ForgetMany";
import { stubDialogs } from "./fakes";

const HOUR = 3_600_000;
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  return {
    name,
    repo: `/src/${name}`,
    status: "stopped",
    agents: 1,
    waiting: { gates: 0, questions: 0, agents: 0 },
    kits: ["default"],
    provider: "claude",
    permission_mode: null,
    without: [],
    ran_seconds: 0,
    running_since: null,
    busy: 0,
    stopped_at: ago(2 * HOUR),
    title: null,
    ...more,
  };
}

const SEVEN = ["lad-97", "lad-95", "lad-88", "lad-85", "lad-80", "lad-71", "lad-67"];

type Call = { method: string; path: string };

let answers: Record<string, () => Response | Promise<Response>>; // "METHOD path" -> the server's answer
let calls: Call[];

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const NOTHING = { open_runs: [], worktrees: [] };

beforeEach(() => {
  stubDialogs();
  answers = {};
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, path });
      const url = new URL(path, "http://lado.test");
      const answer = answers[`${method} ${url.pathname}`];
      if (answer) return answer();
      if (method === "GET" && url.pathname.endsWith("/forget-preview")) return json(NOTHING);
      if (method === "DELETE") return json(NOTHING);
      return json({ detail: `not served: ${method} ${path}` }, 404);
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// The window in the session list's place: the list's route stays while the page under it
// changes, as in the app (Sessions.tsx).
function open(sessions: SessionInfo[], at = "/sessions") {
  const onClose = vi.fn();
  function List() {
    return (
      <>
        <ForgetManyDialog sessions={sessions} onClose={onClose} />
        <Outlet />
      </>
    );
  }
  render(
    <MemoryRouter initialEntries={[at]}>
      <Routes>
        <Route path="/sessions" element={<List />}>
          <Route index element={<p>No session open</p>} />
          <Route path=":name" element={<p>A session open</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
  const dialog = screen.getByRole("dialog", { name: "Forget stopped sessions?" });
  return { dialog, onClose };
}

const forgetButton = (dialog: HTMLElement) =>
  within(dialog).getByRole("button", { name: /^(Forget \d+ sessions?|Forgetting .*)$/ }) as HTMLButtonElement;
const tick = (dialog: HTMLElement, name: string) => within(dialog).getByRole("checkbox", { name: new RegExp(`^${name}\\b`) }) as HTMLInputElement;
const deletes = () => calls.filter((call) => call.method === "DELETE").map((call) => call.path);

test("the window lists every session given, ticked, with when it stopped, and says what forgetting does", async () => {
  const { dialog } = open(SEVEN.map((name) => session(name, name === "lad-95" ? { title: "Phone layout" } : {})));
  expect(dialog.hasAttribute("open")).toBe(true); // modal
  expect(within(dialog).getByText("Their history (messages, runs, notes, gates) is deleted. This cannot be undone.")).toBeTruthy();
  const rows = within(dialog).getAllByRole("listitem");
  expect(rows).toHaveLength(7);
  expect(rows[1].textContent).toContain("Phone layout");
  expect(rows[0].textContent).toContain("stopped 2 h ago");
  expect(forgetButton(dialog).disabled).toBe(true); // the previews still load
  await waitFor(() => expect(forgetButton(dialog).disabled).toBe(false));
  expect(forgetButton(dialog).textContent).toBe("Forget 7 sessions");
  for (const name of SEVEN) {
    expect(tick(dialog, name === "lad-95" ? "Phone layout" : name).checked).toBe(true);
    expect(calls).toContainEqual({ method: "GET", path: `/api/sessions/${name}/forget-preview` });
  }
  expect((within(dialog).getByRole("checkbox", { name: "All 7" }) as HTMLInputElement).checked).toBe(true);
  expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Cancel" }));
});

test("cleared ticks lower the count; All clears and ticks them all; none ticked, the button is off", async () => {
  const { dialog } = open(SEVEN.map((name) => session(name)));
  await waitFor(() => expect(forgetButton(dialog).disabled).toBe(false));
  fireEvent.click(tick(dialog, "lad-97"));
  fireEvent.click(tick(dialog, "lad-67"));
  expect(forgetButton(dialog).textContent).toBe("Forget 5 sessions");
  const all = within(dialog).getByRole("checkbox", { name: "All 7" }) as HTMLInputElement;
  expect(all.checked).toBe(false);
  fireEvent.click(all);
  expect(forgetButton(dialog).textContent).toBe("Forget 7 sessions");
  fireEvent.click(all);
  expect(forgetButton(dialog).textContent).toBe("Forget 0 sessions");
  expect(forgetButton(dialog).disabled).toBe(true);
  fireEvent.click(tick(dialog, "lad-85"));
  expect(forgetButton(dialog).textContent).toBe("Forget 1 session");
});

test("sessions with open runs stay while the switch is off and go with their runs when it is on", async () => {
  answers["GET /api/sessions/lad-88/forget-preview"] = () => json({ open_runs: ["feature/a"], worktrees: [] });
  answers["GET /api/sessions/lad-80/forget-preview"] = () => json({ open_runs: ["feature/b", "fix/c"], worktrees: [] });
  const { dialog } = open(SEVEN.map((name) => session(name)));
  await within(dialog).findByText("1 open run");
  expect(within(dialog).getByText("2 open runs")).toBeTruthy();
  const both = within(dialog).getByRole("checkbox", { name: "Also forget their 3 open runs (lad-88, lad-80)" }) as HTMLInputElement;
  expect(both.checked).toBe(false);
  expect(within(dialog).getByText("While this is off, lad-88 and lad-80 stay.")).toBeTruthy();
  expect(forgetButton(dialog).textContent).toBe("Forget 5 sessions");
  fireEvent.click(both);
  expect(within(dialog).queryByText(/While this is off/)).toBeNull();
  expect(forgetButton(dialog).textContent).toBe("Forget 7 sessions");
  fireEvent.click(both);
  // A session with runs cleared: the switch names only the ticked ones.
  fireEvent.click(tick(dialog, "lad-80"));
  expect(within(dialog).getByRole("checkbox", { name: "Also forget their 1 open run (lad-88)" })).toBeTruthy();
  fireEvent.click(forgetButton(dialog));
  await waitFor(() => expect(deletes()).toHaveLength(5));
  expect(deletes()).toEqual(["lad-97", "lad-95", "lad-85", "lad-71", "lad-67"].map((name) => `/api/sessions/${name}?force=false`));
});

test("with the switch on, only the sessions with open runs are forgotten with force", async () => {
  answers["GET /api/sessions/lad-88/forget-preview"] = () => json({ open_runs: ["feature/a"], worktrees: [] });
  const { dialog, onClose } = open(["lad-97", "lad-88", "lad-85"].map((name) => session(name)));
  fireEvent.click(await within(dialog).findByRole("checkbox", { name: "Also forget their 1 open run (lad-88)" }));
  fireEvent.click(forgetButton(dialog));
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  expect(deletes()).toEqual([
    "/api/sessions/lad-97?force=false",
    "/api/sessions/lad-88?force=true",
    "/api/sessions/lad-85?force=false",
  ]);
});

test("a session whose preview is refused shows the core's reason, unticked and off, and is never forgotten", async () => {
  answers["GET /api/sessions/lad-85/forget-preview"] = () =>
    json({ detail: 'session "lad-85" is not stopped; stop it first with lado stop lad-85' }, 400);
  const { dialog, onClose } = open(["lad-97", "lad-85"].map((name) => session(name)));
  expect(await within(dialog).findByText('session "lad-85" is not stopped; stop it first with lado stop lad-85')).toBeTruthy();
  const refused = tick(dialog, "lad-85");
  expect(refused.checked).toBe(false);
  expect(refused.disabled).toBe(true);
  expect(forgetButton(dialog).textContent).toBe("Forget 1 session");
  fireEvent.click(within(dialog).getByRole("checkbox", { name: "All 2" })); // clears
  fireEvent.click(within(dialog).getByRole("checkbox", { name: "All 2" })); // ticks what can be
  expect(refused.checked).toBe(false);
  fireEvent.click(forgetButton(dialog));
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  expect(deletes()).toEqual(["/api/sessions/lad-97?force=false"]);
});

test("the worktrees the ticked sessions leave on disk are listed under a folded line", async () => {
  answers["GET /api/sessions/lad-97/forget-preview"] = () =>
    json({
      open_runs: [],
      worktrees: [
        { path: "/src/lado/.lado/worktrees/lad-97/a", branch: "lado/lad-97/a" },
        { path: "/src/lado/.lado/worktrees/lad-97/b", branch: "lado/lad-97/b" },
      ],
    });
  answers["GET /api/sessions/lad-85/forget-preview"] = () =>
    json({ open_runs: [], worktrees: [{ path: "/src/lado/.lado/worktrees/lad-85/c", branch: "lado/lad-85/c" }] });
  const { dialog } = open(["lad-97", "lad-85", "lad-71"].map((name) => session(name)));
  const line = await within(dialog).findByText("Left on disk: 3 worktrees of 2 sessions (remove them yourself if you need to)");
  expect(line.closest("details")!.hasAttribute("open")).toBe(false);
  expect(within(dialog).getByText("/src/lado/.lado/worktrees/lad-85/c · branch lado/lad-85/c")).toBeTruthy();
  fireEvent.click(tick(dialog, "lad-97"));
  expect(within(dialog).getByText("Left on disk: 1 worktree of 1 session (remove them yourself if you need to)")).toBeTruthy();
  fireEvent.click(tick(dialog, "lad-85"));
  expect(within(dialog).queryByText(/^Left on disk/)).toBeNull();
});

test("the sessions are forgotten one at a time in the list's order, each reported, and Esc waits", async () => {
  const pending: ((answer: Response) => void)[] = [];
  for (const name of ["lad-97", "lad-85", "lad-71"])
    answers[`DELETE /api/sessions/${name}`] = () => new Promise<Response>((resolve) => pending.push(resolve));
  const { dialog, onClose } = open(["lad-97", "lad-85", "lad-71"].map((name) => session(name)));
  await waitFor(() => expect(forgetButton(dialog).disabled).toBe(false));
  fireEvent.click(forgetButton(dialog));
  await waitFor(() => expect(pending).toHaveLength(1));
  expect(forgetButton(dialog).textContent).toBe("Forgetting 1 of 3…");
  expect(forgetButton(dialog).disabled).toBe(true);
  expect((within(dialog).getByRole("button", { name: "Cancel" }) as HTMLButtonElement).disabled).toBe(true);
  expect(within(dialog).queryByRole("checkbox")).toBeNull(); // the counted sessions only, no ticks
  fireEvent.keyDown(dialog, { key: "Escape" });
  fireEvent(dialog, new Event("cancel", { cancelable: true }));
  expect(onClose).not.toHaveBeenCalled();
  pending[0](json(NOTHING));
  await waitFor(() => expect(pending).toHaveLength(2));
  expect(deletes()).toEqual(["/api/sessions/lad-97?force=false", "/api/sessions/lad-85?force=false"]);
  expect(within(dialog).getAllByRole("listitem")[0].textContent).toContain("forgotten");
  expect(forgetButton(dialog).textContent).toBe("Forgetting 2 of 3…");
  pending[1](json(NOTHING));
  await waitFor(() => expect(pending).toHaveLength(3));
  pending[2](json(NOTHING));
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  expect(await screen.findByText("No session open")).toBeTruthy();
});

test("a refused forget does not stop the others; the window stays with the reason and Close", async () => {
  answers["DELETE /api/sessions/lad-85"] = () => json({ detail: 'session "lad-85" is not stopped; stop it first' }, 400);
  const { dialog, onClose } = open(["lad-97", "lad-85", "lad-71"].map((name) => session(name)));
  await waitFor(() => expect(forgetButton(dialog).disabled).toBe(false));
  fireEvent.click(forgetButton(dialog));
  const close = await within(dialog).findByRole("button", { name: "Close" });
  expect(deletes()).toHaveLength(3);
  expect(within(dialog).getByText('session "lad-85" is not stopped; stop it first')).toBeTruthy();
  expect(within(dialog).queryByRole("button", { name: "Cancel" })).toBeNull();
  expect(within(dialog).queryByRole("button", { name: /^Forget/ })).toBeNull();
  expect(onClose).not.toHaveBeenCalled();
  fireEvent.click(close);
  expect(onClose).toHaveBeenCalledOnce();
});

test("when the session open in the page is forgotten, the page goes to /sessions", async () => {
  answers["DELETE /api/sessions/lad-85"] = () => json({ detail: "refused" }, 400);
  const { dialog } = open(["lad-97", "lad-85"].map((name) => session(name)), "/sessions/lad-97");
  expect(screen.getByText("A session open")).toBeTruthy();
  await waitFor(() => expect(forgetButton(dialog).disabled).toBe(false));
  fireEvent.click(forgetButton(dialog));
  await within(dialog).findByRole("button", { name: "Close" });
  // React Router applies the navigation in a transition, a render after Close.
  expect(await screen.findByText("No session open")).toBeTruthy();
});

test("another session open in the page stays", async () => {
  const { dialog, onClose } = open([session("lad-97")], "/sessions/lado");
  await waitFor(() => expect(forgetButton(dialog).disabled).toBe(false));
  fireEvent.click(forgetButton(dialog));
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  expect(screen.getByText("A session open")).toBeTruthy();
});

test("Cancel and Esc close the window with nothing forgotten", async () => {
  const first = open([session("lad-97")]);
  fireEvent.click(within(first.dialog).getByRole("button", { name: "Cancel" }));
  expect(first.onClose).toHaveBeenCalledOnce();
  cleanup();
  const second = open([session("lad-97")]);
  fireEvent.keyDown(second.dialog, { key: "Escape" });
  expect(second.onClose).toHaveBeenCalledOnce();
  expect(deletes()).toEqual([]);
});
