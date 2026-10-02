// The UI's only way to LADO: the server's API. Types come from its OpenAPI schema
// (api.gen.ts, made by `make web-types`).
import type { components } from "./api.gen";

export type SessionInfo = components["schemas"]["SessionInfo"];
export type SessionStatus = components["schemas"]["SessionStatus"];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  const answer = await fetch(path, { credentials: "same-origin" });
  if (!answer.ok) {
    const body = await answer.json().catch(() => null);
    throw new ApiError(answer.status, body?.detail ?? `${answer.status} ${answer.statusText}`);
  }
  return (await answer.json()) as T;
}

export const getSessions = () => get<SessionInfo[]>("/api/sessions");
