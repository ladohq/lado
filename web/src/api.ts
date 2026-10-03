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

async function refused(answer: Response): Promise<ApiError> {
  const body = await answer.json().catch(() => null);
  const error = new ApiError(answer.status, body?.detail ?? `${answer.status} ${answer.statusText}`);
  if (error.status === 401) denied?.(error.message);
  return error;
}

async function get<T>(path: string): Promise<T> {
  const answer = await fetch(path, { credentials: "same-origin" });
  if (!answer.ok) throw await refused(answer);
  return (await answer.json()) as T;
}

export type AgentInfo = components["schemas"]["AgentInfo"];
export type History = components["schemas"]["History"];

export const getSessions = () => get<SessionInfo[]>("/api/sessions");

const agentsPath = (session: string) => `${sessionPath(session)}/agents`;

export const getAgents = (session: string) => get<AgentInfo[]>(agentsPath(session));

// The agent's window: its last lines and whether it shows a full-screen program.
export const getHistory = (session: string, agent: string, lines = 2000) =>
  get<History>(`${agentsPath(session)}/${encodeURIComponent(agent)}/history?lines=${lines}`);

export type MessageInfo = components["schemas"]["MessageInfo"];
export type Sent = components["schemas"]["Sent"];

export const HUMAN = "human"; // the human as a participant of LADO's messages

// A request that changes something: the browser sends its Origin, which the server checks.
async function post<T>(path: string, body?: unknown): Promise<T> {
  const answer = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!answer.ok) throw await refused(answer);
  return (await answer.json()) as T;
}

const sessionPath = (session: string) => `/api/sessions/${encodeURIComponent(session)}`;

// The session's messages, oldest first: with the human and between the agents.
export const getMessages = (session: string) => get<MessageInfo[]>(`${sessionPath(session)}/messages`);

export type RunEventInfo = components["schemas"]["RunEventInfo"];

// What happened to the session's flow runs, oldest first.
export const getRunEvents = (session: string) => get<RunEventInfo[]>(`${sessionPath(session)}/events`);

export type GateInfo = components["schemas"]["GateInfo"];

// The session's flow gates, open and closed, oldest first.
export const getGates = (session: string) => get<GateInfo[]>(`${sessionPath(session)}/gates`);

// The human's answer to an open gate: one of its options and a comment for the next step.
export const answerGate = (session: string, id: number, option: string, comment: string) =>
  post<Sent>(`${sessionPath(session)}/gates/${id}/answer`, { option, comment });

// The human's text to an agent of the session (default: the supervisor).
export const writeMessage = (session: string, text: string) =>
  post<Sent>(`${sessionPath(session)}/messages`, { text });

export const answerQuestion = (session: string, id: number, answer: { choice?: string; text?: string }) =>
  post<Sent>(`${sessionPath(session)}/questions/${id}/answer`, answer);

export const dismissQuestion = (session: string, id: number) =>
  post<Sent>(`${sessionPath(session)}/questions/${id}/dismiss`);

// Why the server refuses the event stream at `path`: an ApiError, or nothing when it would
// open now. Reads only the answer's head; an open stream is closed at once.
export async function probeStream(path: string): Promise<void> {
  const abort = new AbortController();
  const answer = await fetch(path, { credentials: "same-origin", signal: abort.signal });
  if (!answer.ok) throw await refused(answer);
  abort.abort();
}
