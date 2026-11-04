// The server of Settings → Models in the component tests (ModelSettings.test.tsx,
// ModelSources.test.tsx): the entries, the CLIs' rows and lists, and the servers' probes,
// each request recorded; a test sets an answer of its own by "METHOD path".
import { vi } from "vitest";

import type { ConfiguredModelInfo, ModelServerInfo, ModelSettings, ProbeInfo, ProviderLogins } from "./api";
import { claudeRow, cli, codexRow, opencodeRow } from "./fakes";

export type Call = { method: string; path: string; body: unknown };
type Added = { name: string | null; cli: string; model: string; server: string | null };

export const LMSTUDIO_PROBE: ProbeInfo = {
  kind: "LM Studio",
  address: "http://localhost:1234",
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
      const given = body as Added;
      if (given.name && this.taken(given.name)) return refusal(`the name is taken by the model "${given.name}"`, "name");
      const added = model(given.name ?? this.named(given), given.cli, this.title(given.cli), given.model, given.server);
      this.entries = { ...this.entries, models: [...this.entries.models, added] };
      return json({ model: added, check: { kind: "ok", text: "fine", field: "", name: "" } });
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
    if (where === "/api/models/check") {
      const given = body as Added;
      return json({ kind: "ok", text: "in the list", field: "", name: given.name ?? this.named(given) });
    }
    if (where === "/api/model-servers/check") {
      // The core's rules in short: a name taken; nothing answers at a port 1243; a gateway
      // (`gw` in its address) asks for a key, takes "right" or a Change's kept key; a key over
      // http:// to a host not on the machine; another server at the same address.
      const given = body as { name: string; address: string; key: string | null; key_typed: boolean; replace: boolean };
      const refusals = [];
      const taken = this.entries.servers.find((s) => s.name.toLowerCase() === given.name.toLowerCase());
      if (taken && !given.replace) refusals.push(detail(`a model server "${taken.name}" is saved already`, "name"));
      const address = given.address.trim();
      const url = /^https?:\/\//.test(address) ? address : `http://${address}`;
      const host = url.replace(/^https?:\/\//, "").split(/[:/]/)[0];
      const kept = given.replace && !given.key_typed && given.key === null && taken?.has_key; // Change sends it
      const warnings =
        (given.key_typed || kept) && url.startsWith("http://") && host !== "localhost"
          ? [`the key goes to ${host} over plain http://, unencrypted`]
          : [];
      if (!address) return json({ probe: null, refusals, warnings: [], notes: [] });
      if (address.includes(":1243"))
        refusals.push(detail(`${url} does not answer (connection refused)`, "address"));
      else if (address.includes("gw") && given.key !== "right" && !kept)
        refusals.push(detail(given.key === null ? `${url} asks for a key (401): enter it in Key` : `${url} refused the key (401)`, "key"));
      const probe = refusals.some((r) => r.field !== "name") ? null : { ...LMSTUDIO_PROBE, kind: address.includes("gw") ? "LiteLLM" : "LM Studio", address: url };
      const notes = probe
        ? this.entries.servers
            .filter((s) => s.address === url && !(given.replace && s === taken))
            .map((s) => `same address as model server "${s.name}"`)
        : [];
      return json({ probe, refusals, warnings, notes });
    }
    const server = where.match(/^\/api\/model-servers\/(.+)$/);
    if (server && method === "DELETE") {
      const confirmed = new URLSearchParams(path.split("?")[1] ?? "").getAll("confirmed");
      const own = this.entries.models.filter((m) => m.server === server[1]).map((m) => m.name);
      if ([...own].sort().join("\n") !== [...confirmed].sort().join("\n"))
        return refusal(`model server "${server[1]}" has other models now: ${own.join(", ")}; nothing was removed`);
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

  title = (cli: string) => this.logins.find((r) => r.cli.name === cli)?.cli.title ?? cli;
  taken = (name: string) => this.entries.models.some((m) => m.name.toLowerCase() === name.toLowerCase());

  // The core's default name in short: `<model> · <server> · <CLI title>` on a server, else
  // the model, then ` (default)`; ` (2)` when taken.
  named(given: Added): string {
    const base = given.server ? `${given.model} · ${given.server} · ${this.title(given.cli)}` : `${given.model} (default)`;
    return this.taken(base) ? `${base} (2)` : base;
  }

  of(method: string, start: string): Call[] {
    return this.calls.filter((c) => c.method === method && c.path.startsWith(start));
  }
}

export const detail = (message: string, field = "", hint = "", warnings: string[] = []) => ({
  message,
  hint,
  field,
  warnings,
});

export const refusal = (message: string, field = "", hint = "", warnings: string[] = []) =>
  new Response(JSON.stringify({ detail: detail(message, field, hint, warnings) }), { status: 400 });
