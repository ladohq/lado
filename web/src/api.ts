// The UI's only way to LADO: the server's API. Types come from its OpenAPI schema
// (api.gen.ts, made by `make web-types`).
import type { components } from "./api.gen";

export type SessionInfo = components["schemas"]["SessionInfo"];
export type SessionStatus = components["schemas"]["SessionStatus"];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly detail: unknown = message, // the answer's `detail`, an object for some (Taken, Refused)
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
  const detail = body?.detail ?? `${answer.status} ${answer.statusText}`;
  const text = typeof detail === "string" ? detail : (detail.message ?? JSON.stringify(detail));
  const error = new ApiError(answer.status, text, detail);
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

export type WaitingItem = components["schemas"]["WaitingItem"];

// What waits for the human in every session not stopped, oldest first (Needs you).
export const getWaiting = () => get<WaitingItem[]>("/api/waiting");

export type Health = components["schemas"]["Health"];

// The server's LADO version; needs no token.
export const getHealth = () => get<Health>("/api/health");

const agentsPath = (session: string) => `${sessionPath(session)}/agents`;

export const getAgents = (session: string) => get<AgentInfo[]>(agentsPath(session));

const agentPath = (session: string, agent: string) => `${agentsPath(session)}/${encodeURIComponent(agent)}`;

// The agent's window: its last lines and whether it shows a full-screen program.
export const getHistory = (session: string, agent: string, lines = 2000) =>
  get<History>(`${agentPath(session, agent)}/history?lines=${lines}`);

export type AgentDetails = components["schemas"]["AgentDetails"];
export type WorkInfo = components["schemas"]["WorkInfo"];
export type FinishPreviewInfo = components["schemas"]["FinishPreviewInfo"];
export type FinishedAgentInfo = components["schemas"]["FinishedAgentInfo"];

// The agent's whole task and where its work stands in git now (asked anew each time).
export const getAgentDetails = (session: string, agent: string) =>
  get<AgentDetails>(`${agentPath(session, agent)}/details`);

// The session's finished workers, newest first.
export const getFinishedAgents = (session: string) => get<FinishedAgentInfo[]>(`${agentsPath(session)}/finished`);

// What finishing the worker would do now, as the core says.
export const getFinishPreview = (session: string, agent: string) =>
  get<FinishPreviewInfo>(`${agentPath(session, agent)}/finish-preview`);

export const finishAgent = (session: string, agent: string, discard: boolean) =>
  post<Sent>(`${agentPath(session, agent)}/finish`, { discard });

export type MessageInfo = components["schemas"]["MessageInfo"];
export type Sent = components["schemas"]["Sent"];

export const HUMAN = "human"; // the human as a participant of LADO's messages

// A request that changes something: the browser sends its Origin, which the server checks.
async function post<T>(path: string, body?: unknown, method = "POST"): Promise<T> {
  const answer = await fetch(path, {
    method,
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

export type RunInfo = components["schemas"]["RunInfo"];
export type NoteInfo = components["schemas"]["NoteInfo"];

// The session's flow runs, open and closed, newest first.
export const getRuns = (session: string) => get<RunInfo[]>(`${sessionPath(session)}/runs`);

// The notes of the session's flow runs, oldest first: each is a step a run took.
export const getNotes = (session: string) => get<NoteInfo[]>(`${sessionPath(session)}/notes`);

// The human's answer to an open gate: one of its options and a comment for the next step.
export const answerGate = (session: string, id: number, option: string, comment: string) =>
  post<Sent>(`${sessionPath(session)}/gates/${id}/answer`, { option, comment });

// The human's text to an agent of the session (default: the supervisor).
export const writeMessage = (session: string, text: string, to?: string) =>
  post<Sent>(`${sessionPath(session)}/messages`, to === undefined ? { text } : { to, text });

export const answerQuestion = (session: string, id: number, answer: { choice?: string; text?: string }) =>
  post<Sent>(`${sessionPath(session)}/questions/${id}/answer`, answer);

export const dismissQuestion = (session: string, id: number) =>
  post<Sent>(`${sessionPath(session)}/questions/${id}/dismiss`);

// Launch and session control (docs/design/ui.md, Launch and session control).

export type FolderInfo = components["schemas"]["FolderInfo"];
export type RecentFolder = components["schemas"]["RecentFolder"];
export type KitInfo = components["schemas"]["KitInfo"];
export type ProviderInfo = components["schemas"]["ProviderInfo"];
export type Launch = components["schemas"]["Launch"];
export type Resume = components["schemas"]["Resume"];
export type Started = components["schemas"]["Started"];
export type Taken = components["schemas"]["Taken"];
export type Refused = components["schemas"]["Refused"];
export type StopPreview = components["schemas"]["StopPreview"];
export type Stopped = components["schemas"]["Stopped"];
export type ForgetPreview = components["schemas"]["ForgetPreview"];
export type Forgotten = components["schemas"]["Forgotten"];

const query = (params: Record<string, string>) => new URLSearchParams(params).toString();

// A folder as the server checks it for a session: the core's reason when it will not do.
export const getFolder = (path: string) => get<FolderInfo>(`/api/folders?${query({ path })}`);

export const getRecentFolders = () => get<RecentFolder[]>("/api/folders/recent");

// The kits a session of the folder `where` can take, one per name.
export const getKits = (where: string | null) =>
  get<KitInfo[]>(where ? `/api/kits?${query({ where })}` : "/api/kits");

// LADO's providers, each one's CLI checked anew.
export const getProviders = () => get<ProviderInfo[]>("/api/providers");

export const startSession = (launch: Launch) => post<Started>("/api/sessions", launch);

export const resumeSession = (session: string, resume: Resume) =>
  post<Started>(`${sessionPath(session)}/resume`, resume);

export const getStopPreview = (session: string) => get<StopPreview>(`${sessionPath(session)}/stop-preview`);

export const stopSession = (session: string) => post<Stopped>(`${sessionPath(session)}/stop`);

export const getForgetPreview = (session: string) => get<ForgetPreview>(`${sessionPath(session)}/forget-preview`);

export const forgetSession = (session: string, force: boolean) =>
  post<Forgotten>(`${sessionPath(session)}?${query({ force: String(force) })}`, undefined, "DELETE");

// Why the server refuses the event stream at `path`: an ApiError, or nothing when it would
// open now. Reads only the answer's head; an open stream is closed at once.
export async function probeStream(path: string): Promise<void> {
  const abort = new AbortController();
  const answer = await fetch(path, { credentials: "same-origin", signal: abort.signal });
  if (!answer.ok) throw await refused(answer);
  abort.abort();
}
