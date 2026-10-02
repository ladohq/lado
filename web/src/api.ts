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

// Who hears about a 401: the shell, the one place that tells the human how to get in.
let denied: ((detail: string) => void) | null = null;

export function onDenied(listener: (detail: string) => void): () => void {
  denied = listener;
  return () => {
    if (denied === listener) denied = null;
  };
}

async function get<T>(path: string): Promise<T> {
  const answer = await fetch(path, { credentials: "same-origin" });
  if (!answer.ok) {
    const body = await answer.json().catch(() => null);
    const error = new ApiError(answer.status, body?.detail ?? `${answer.status} ${answer.statusText}`);
    if (error.status === 401) denied?.(error.message);
    throw error;
  }
  return (await answer.json()) as T;
}

export const getSessions = () => get<SessionInfo[]>("/api/sessions");
