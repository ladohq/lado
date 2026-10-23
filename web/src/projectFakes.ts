// A fake server of the Projects section for the UI's unit tests (not part of the bundle:
// only tests import this file): its projects in memory, every request recorded.
import { vi } from "vitest";

import type { ProjectInfo, ProjectSummary, SessionInfo } from "./api";

export type Asked = { method: string; path: string; body: unknown };

export const NONE = { gates: 0, questions: 0, agents: 0 };

export function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  return {
    name,
    repo: `/ws/projects/shop/${name}`,
    status: "running",
    agents: 1,
    waiting: NONE,
    kits: ["default"],
    provider: "claude",
    permission_mode: null,
    without: [],
    ran_seconds: 0,
    running_since: null,
    stopped_at: null,
    busy: 0,
    title: null,
    project: null,
    ...more,
  };
}

export function project(id: string, more: Partial<ProjectInfo> = {}): ProjectInfo {
  return {
    id,
    title: null,
    folder: `/ws/projects/${id}`,
    found: true,
    repos: [],
    variables: [],
    secrets: [],
    running: [],
    overrides: [],
    unused: [],
    ...more,
  };
}

const repo = (name: string) => ({ name, path: `/ws/projects/shop/${name}`, remote: null, branch: "main" });

// Shop (two repositories, two sessions running), ACME CRM (one) and sandbox (its folder gone).
export function threeProjects(): Record<string, ProjectInfo> {
  return {
    acme: project("acme", { title: "ACME CRM", repos: [repo("crm")] }),
    sandbox: project("sandbox", { found: false }),
    shop: project("shop", {
      title: "Shop",
      repos: [repo("backend"), repo("frontend")],
      running: ["shop-backend", "shop-frontend"],
      variables: [{ name: "BOARD_URL", value: "https://board" }],
      secrets: ["GH_TOKEN"],
    }),
  };
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

const summary = (one: ProjectInfo): ProjectSummary => ({
  id: one.id,
  title: one.title,
  folder: one.folder,
  found: one.found,
  repos: one.repos.length,
  running: one.running,
});

// The server: `projects` and `sessions` change as a test or a request changes them;
// `refuse` answers a change with a 400 of its text when it returns one; `suggest` answers
// GET /api/project-id.
export class FakeProjects {
  asked: Asked[] = [];
  refuse: (asked: Asked) => string | null = () => null;
  suggest: (title: string | null, id: string | null) => { id: string | null; folder: string | null; problem: string | null } = (
    title,
    id,
  ) => {
    const made = id ?? (title ?? "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
    return {
      id: made || null,
      folder: made ? `/ws/projects/${made}` : null,
      problem: made in this.projects ? `project ${made} exists` : null,
    };
  };

  constructor(
    public projects: Record<string, ProjectInfo> = threeProjects(),
    public sessions: SessionInfo[] = [],
  ) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, init?: RequestInit) => this.answer(path, init)),
    );
  }

  calls(method: string, path: string): Asked[] {
    return this.asked.filter((one) => one.method === method && one.path === path);
  }

  private answer(path: string, init?: RequestInit): Response {
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    const asked = { method, path, body };
    this.asked.push(asked);
    if (path === "/api/health") return json({ ok: true, version: "0" });
    if (path === "/api/update") return json({ current: "0", latest: null, available: null, checked_at: null });
    if (path.startsWith("/api/events")) return json("");
    if (path === "/api/sessions") return json(this.sessions);
    if (path.startsWith("/api/sessions/")) return json(path.endsWith("/about") ? null : []);
    if (path.startsWith("/api/project-id?")) {
      const query = new URLSearchParams(path.split("?")[1]);
      return json(this.suggest(query.get("title"), query.get("id")));
    }
    if (path === "/api/projects" && method === "GET") {
      return json(
        Object.values(this.projects)
          .sort((a, b) => a.id.localeCompare(b.id))
          .map(summary),
      );
    }
    const refusal = method === "GET" ? null : this.refuse(asked);
    if (refusal !== null) return json({ detail: refusal }, 400);
    if (path === "/api/projects" && method === "POST") {
      const made = project(body.id, { title: body.title ?? null });
      this.projects[body.id] = made;
      return json(made);
    }
    const [, , , id, kind, name] = path.split("/").map(decodeURIComponent);
    const found = this.projects[id];
    if (!found) return json({ detail: `unknown project "${id}"` }, 404);
    if (kind === undefined) return json(found);
    if (kind === "variables") {
      const variables = found.variables.filter((one) => one.name !== name);
      if (method === "PUT") variables.push({ name, value: body.value });
      found.variables = variables.sort((a, b) => a.name.localeCompare(b.name));
    } else if (kind === "secrets") {
      const secrets = found.secrets.filter((one) => one !== name);
      if (method === "PUT") secrets.push(name);
      found.secrets = secrets.sort();
      found.unused = found.unused.filter((one) => one.name !== name);
    }
    this.projects[id] = { ...found };
    return json({ project: this.projects[id], running: found.running });
  }
}
