// The server of Settings → Models in the component tests (ModelSettings.test.tsx,
// ModelSources.test.tsx): the entries, the CLIs' rows and lists, and the servers' probes,
// each request recorded; a test sets an answer of its own by "METHOD path".
import { vi } from "vitest";

import type { ConfiguredModelInfo, ModelServerInfo, ModelSettings, ProbeInfo, ProviderLogins } from "./api";
import { claudeRow, cli, codexRow, opencodeRow } from "./fakes";

export type Call = { method: string; path: string; body: unknown };

export const LMSTUDIO_PROBE: ProbeInfo = {
  models: ["qwen3-8b", "text-embedding-nomic"],
  models_why: "",
  embeddings: ["text-embedding-nomic"],
  apis_why: "",
  clis: [
    { name: "kilo", title: "Kilo CLI", api: "chat completions" },
    { name: "opencode", title: "OpenCode", api: "chat completions" },
    { name: "codex", title: "Codex CLI", api: "Responses API" },
  ],
};

export const LMSTUDIO: ModelServerInfo = {
  name: "LM Studio дома",
  address: "http://localhost:1234",
  kind: "LM Studio",
  has_key: false,
};

export function kiloRow(installed = false): ProviderLogins {
  return { ...opencodeRow(), cli: { ...cli("kilo", "Kilo CLI"), installed } };
}

export const model = (name: string, cliName: string, title: string, m: string, server: string | null = null) =>
  ({ name, cli: cliName, cli_title: title, model: m, server }) satisfies ConfiguredModelInfo;

export class ModelServer {
  entries: ModelSettings = { models: [], servers: [] };
  logins: ProviderLogins[] = [claudeRow({ login: { ...claudeRow().login, state: "yes" } }), codexRow(), opencodeRow(), kiloRow()];
  probes: Record<string, ProbeInfo | (() => Response | Promise<Response>)> = {};
  calls: Call[] = [];
  answers: Record<string, (body: unknown) => Response | Promise<Response>> = {};

  install() {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        const body = init?.body ? JSON.parse(String(init.body)) : undefined;
        this.calls.push({ method, path, body });
        const own = this.answers[`${method} ${path.split("?")[0]}`];
        if (own) return own(body);
        return this.answer(method, decodeURIComponent(path), body);
      }),
    );
  }

  answer(method: string, path: string, body: unknown): Response | Promise<Response> {
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    const [where] = path.split("?");
    if (where === "/api/model-settings") return json(this.entries);
    if (where === "/api/providers/logins") return json({ providers: this.logins, checking: false, environment: "" });
    if (where === "/api/providers/claude/models")
      return json({
        aliases: ["sonnet", "opus"],
        models: null,
        why: "Claude Code gives no list of models beyond its aliases",
        check: { kind: "default", text: "", field: "" },
      });
    if (where.startsWith("/api/providers/") && where.endsWith("/models"))
      return json({ aliases: [], models: ["gpt-5-codex"], why: "", check: { kind: "default", text: "", field: "" } });
    const probed = where.match(/^\/api\/model-servers\/(.+)\/probe$/);
    if (probed && method === "POST") {
      const found = this.probes[probed[1]];
      if (typeof found === "function") return found();
      return found ? json(found) : json({ detail: { message: "no", hint: "", field: "", warnings: [] } }, 400);
    }
    if (where === "/api/models" && method === "POST") {
      const given = body as { name: string | null; cli: string; model: string; server: string | null };
      const title = this.logins.find((r) => r.cli.name === given.cli)?.cli.title ?? given.cli;
      const added = model(given.name ?? `${given.model} (default)`, given.cli, title, given.model, given.server);
      this.entries = { ...this.entries, models: [...this.entries.models, added] };
      return json({ model: added, check: { kind: "ok", text: "fine", field: "" } });
    }
    const named = where.match(/^\/api\/models\/(.+)$/);
    if (named && method === "DELETE") {
      this.entries = { ...this.entries, models: this.entries.models.filter((m) => m.name !== named[1]) };
      return json(this.entries);
    }
    if (named && method === "PATCH") {
      const to = (body as { name: string }).name;
      this.entries = {
        ...this.entries,
        models: this.entries.models.map((m) => (m.name === named[1] ? { ...m, name: to } : m)),
      };
      return json(this.entries);
    }
    if (where === "/api/models/check") return json({ kind: "ok", text: "in the list", field: "" });
    const server = where.match(/^\/api\/model-servers\/(.+)$/);
    if (server && method === "DELETE") {
      this.entries = {
        models: this.entries.models.filter((m) => m.server !== server[1]),
        servers: this.entries.servers.filter((s) => s.name !== server[1]),
      };
      return json(this.entries);
    }
    if (where === "/api/model-servers" && method === "POST") {
      const given = body as { name: string; address: string };
      const saved = { ...LMSTUDIO, name: given.name, address: given.address };
      this.entries = { ...this.entries, servers: [...this.entries.servers, saved] };
      return json({ server: saved, probe: LMSTUDIO_PROBE, notes: [], warnings: [], replaced: false });
    }
    return json({ detail: `no fake for ${method} ${path}` }, 404);
  }

  of(method: string, start: string): Call[] {
    return this.calls.filter((c) => c.method === method && c.path.startsWith(start));
  }
}

export const refusal = (message: string, field = "", hint = "", warnings: string[] = []) =>
  new Response(JSON.stringify({ detail: { message, hint, field, warnings } }), { status: 400 });
