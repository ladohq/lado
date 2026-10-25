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

export const getSessions = () => get<SessionInfo[]>("/api/sessions");

// Set the session's title, or clear it with null; the answer is the session as stored.
export const setSessionTitle = (session: string, title: string | null) =>
  post<SessionInfo>(`/api/sessions/${encodeURIComponent(session)}/title`, { title }, "PUT");

export type WaitingItem = components["schemas"]["WaitingItem"];

// What waits for the human in every session not stopped, oldest first (Needs you).
export const getWaiting = () => get<WaitingItem[]>("/api/waiting");

export type Health = components["schemas"]["Health"];

// The server's LADO version; needs no token.
export const getHealth = () => get<Health>("/api/health");

export type UpdateInfo = components["schemas"]["UpdateInfo"];

// Whether a newer LADO is out (the server looks once a day), whether this one can update
// itself now, and the latest update's result.
export const getUpdate = () => get<UpdateInfo>("/api/update");

// The same, the server looking at PyPI now.
export const checkUpdateNow = () => post<UpdateInfo>("/api/update/check");

export type UpdatePlan = components["schemas"]["UpdatePlan"];
export type UpdateStarted = components["schemas"]["UpdateStarted"];
export type UpdateResultInfo = components["schemas"]["UpdateResultInfo"];

// What an update to the latest LADO would do (409: none is newer).
export const getUpdatePlan = () => get<UpdatePlan>("/api/update/plan");

// Start `lado update`: it stops this server within seconds.
export const startUpdate = (to: string) => post<UpdateStarted>("/api/update", { to });

export type TelemetryInfo = components["schemas"]["TelemetryInfo"];
export type TelemetryPreview = components["schemas"]["TelemetryPreview"];

// Whether LADO sends usage statistics, and whether to ask the human (the banner).
export const getTelemetry = () => get<TelemetryInfo>("/api/telemetry");

// The human's choice, as `lado telemetry on|off` (409 while the environment switches it off).
export const chooseTelemetry = (choice: "on" | "off") => post<TelemetryInfo>("/api/telemetry", { choice });

// What the next send posts, as `lado telemetry show` prints it.
export const getTelemetryPreview = () => get<TelemetryPreview>("/api/telemetry/preview");

export type SystemInfo = components["schemas"]["SystemInfo"];

// The system panel's facts and the report to copy.
export const getSystem = () => get<SystemInfo>("/api/system");

export type AccessInfo = components["schemas"]["AccessInfo"];

// The link that opens LADO on another device, or why there is none; a new one logs every
// other browser out, and the answer sets this one's cookie.
export const getAccess = () => get<AccessInfo>("/api/access");
export const newAccessToken = () => post<AccessInfo>("/api/access/new-token");

export type BugReport = components["schemas"]["BugReport"];

// The Report a bug page: the report with the page's browser line, and its GitHub link.
export const getBugReport = (browser: string) =>
  get<BugReport>(`/api/bug-report?browser=${encodeURIComponent(browser)}`);

const agentsPath = (session: string) => `${sessionPath(session)}/agents`;

export const getAgents = (session: string) => get<AgentInfo[]>(agentsPath(session));

const agentPath = (session: string, agent: string) => `${agentsPath(session)}/${encodeURIComponent(agent)}`;

export type AgentDetails = components["schemas"]["AgentDetails"];
export type WorkInfo = components["schemas"]["WorkInfo"];
export type FinishPreviewInfo = components["schemas"]["FinishPreviewInfo"];

// The agent's whole task and where its work stands in git now (asked anew each time).
export const getAgentDetails = (session: string, agent: string) =>
  get<AgentDetails>(`${agentPath(session, agent)}/details`);

// What finishing the worker would do now, as the core says.
export const getFinishPreview = (session: string, agent: string) =>
  get<FinishPreviewInfo>(`${agentPath(session, agent)}/finish-preview`);

export const finishAgent = (session: string, agent: string, discard: boolean) =>
  post<Sent>(`${agentPath(session, agent)}/finish`, { discard });

export type MessageInfo = components["schemas"]["MessageInfo"];
export type Sent = components["schemas"]["Sent"];

export const HUMAN = "human"; // the human as a participant of LADO's messages
export const LADO = "lado"; // LADO itself, as the sender of its notices and the actor of run events

// A request that changes something: the browser sends its Origin, which the server checks.
async function post<T>(path: string, body?: unknown, method = "POST"): Promise<T> {
  const answer = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!answer.ok) throw await refused(answer);
  if (answer.status === 204) return undefined as T;
  return (await answer.json()) as T;
}

const sessionPath = (session: string) => `/api/sessions/${encodeURIComponent(session)}`;

export type MessagePage = components["schemas"]["MessagePage"];

// Which of a session's messages a page takes (the server's filter): from and to `with` or
// `agent`, ids between the cursors `after` and `before`, made from the second of `since` to
// the end of the second of `until`; the latest `limit` of them, all without one.
export type MessageQuery = {
  with?: "human";
  agent?: string;
  before?: number;
  after?: number;
  since?: string;
  until?: string;
  limit?: number;
};

// A page of the session's messages, oldest first, and whether earlier ones match.
export const getMessages = (session: string, given: MessageQuery = {}) => {
  const params = Object.entries(given)
    .filter(([, value]) => value !== undefined)
    .map(([key, value]) => [key, String(value)]);
  const search = params.length ? `?${new URLSearchParams(params)}` : "";
  return get<MessagePage>(`${sessionPath(session)}/messages${search}`);
};

export type RunEventInfo = components["schemas"]["RunEventInfo"];

// What happened to the session's flow runs, oldest first.
export const getRunEvents = (session: string) => get<RunEventInfo[]>(`${sessionPath(session)}/events`);

export type GateInfo = components["schemas"]["GateInfo"];
// The lead's recommendation on a gate or a question (Recommendation.tsx).
export type RecommendationInfo = components["schemas"]["RecommendationInfo"];

// The session's flow gates, open and closed, oldest first.
export const getGates = (session: string) => get<GateInfo[]>(`${sessionPath(session)}/gates`);

export type RunInfo = components["schemas"]["RunInfo"];
export type NoteInfo = components["schemas"]["NoteInfo"];

// The session's flow runs, open and closed, newest first.
export const getRuns = (session: string) => get<RunInfo[]>(`${sessionPath(session)}/runs`);

// The notes of the session's flow runs, oldest first: each is a step a run took.
export const getNotes = (session: string) => get<NoteInfo[]>(`${sessionPath(session)}/notes`);

export type ArtifactInfo = components["schemas"]["ArtifactInfo"];
export type RecordInfo = components["schemas"]["RecordInfo"];
export type RecordView = components["schemas"]["RecordView"];
export type AttachmentInfo = components["schemas"]["AttachmentInfo"];
// The session's artifacts, each as of its latest record.
export const getArtifacts = (session: string) => get<ArtifactInfo[]>(`${sessionPath(session)}/artifacts`);
// One artifact with its latest record.
export const getArtifact = (session: string, id: string) =>
  get<ArtifactInfo>(`${sessionPath(session)}/artifacts/${encodeURIComponent(id)}`);
// A record with its artifact as it is now.
export const getRecord = (session: string, record: string) =>
  get<RecordView>(`${sessionPath(session)}/records/${encodeURIComponent(record)}`);
// The address of a record's content (its bytes, under the server's sandbox), or its download.
export const contentPath = (session: string, record: string, download = false) =>
  `${sessionPath(session)}/records/${encodeURIComponent(record)}/content${download ? "?download=1" : ""}`;
// A record's content as an answer, for the viewer to read; a refusal is an ApiError.
export async function getContent(session: string, record: string, signal?: AbortSignal): Promise<Response> {
  const answer = await fetch(contentPath(session, record), { credentials: "same-origin", signal });
  if (!answer.ok) throw await refused(answer);
  return answer;
}
// The human's answer to an open gate: one of its options and a comment for the next step,
// with the full names of the files uploaded for it.
export const answerGate = (session: string, id: number, option: string, comment: string, artifacts: string[] = []) =>
  post<Sent>(`${sessionPath(session)}/gates/${id}/answer`, {
    option,
    comment,
    ...(artifacts.length ? { artifacts } : {}),
  });

// The human's text to an agent of the session (default: the supervisor), with the full
// names of the files uploaded for it.
export const writeMessage = (session: string, text: string, to?: string, artifacts: string[] = []) =>
  post<Sent>(`${sessionPath(session)}/messages`, {
    ...(to === undefined ? {} : { to }),
    text,
    ...(artifacts.length ? { artifacts } : {}),
  });

export type Limits = components["schemas"]["Limits"];

// What the composer checks before an upload and which files an agent reads: the server's.
export const getLimits = () => get<Limits>("/api/limits");

// The human's file as an artifact of the session's scope, its bytes as the body; the same
// file again gives the record it has.
export async function uploadFile(session: string, file: File, name: string): Promise<ArtifactInfo> {
  const answer = await fetch(`${sessionPath(session)}/artifacts?file_name=${encodeURIComponent(name)}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/octet-stream" },
    body: file,
  });
  if (!answer.ok) throw await refused(answer);
  return (await answer.json()) as ArtifactInfo;
}

// A reply sends the full names of the files uploaded for it only when it has some, as a
// message does.
export type Reply = Omit<components["schemas"]["Reply"], "artifacts"> & { artifacts?: string[] };

// The human's replies to open questions of one agent (a tab of the waiting card): all or
// none, handed over to the agent together.
export const answerQuestions = (session: string, answers: Reply[]) =>
  post<Sent>(`${sessionPath(session)}/answers`, { answers });

// Launch and session control (docs/design/ui.md, Launch and session control).

export type FolderInfo = components["schemas"]["FolderInfo"];
export type RecentFolder = components["schemas"]["RecentFolder"];
export type Workspace = components["schemas"]["Workspace"];
export type KitInfo = components["schemas"]["KitInfo"];
export type ProviderInfo = components["schemas"]["ProviderInfo"];
export type SessionAbout = components["schemas"]["SessionAbout"];
export type RepoInfo = components["schemas"]["RepoInfo"];
export type SessionKitInfo = components["schemas"]["SessionKitInfo"];
export type ProviderSuggestion = components["schemas"]["ProviderSuggestion"];
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

export const getWorkspace = () => get<Workspace>("/api/repos-folder");

export type ScratchTarget = components["schemas"]["ScratchTarget"];

// A fresh start of the name `text` in `path` (else the name's default folder): the names,
// the folder's state and git's author, as the core finds them.
export const getScratchTarget = (text: string, path: string | null) =>
  get<ScratchTarget>(`/api/scratch-target?${query(path ? { text, path } : { text })}`);

export type RemoteInfo = components["schemas"]["RemoteInfo"];
export type CloneTarget = components["schemas"]["CloneTarget"];
export type CloneRefused = components["schemas"]["CloneRefused"];
export type CloneStart = components["schemas"]["CloneStart"];
export type CloneJob = components["schemas"]["CloneJob"];

// A remote's branches, its default one first (400 CloneRefused: why it cannot be read); for a
// clone into `project`, listed in that project's variables and secrets (404: no such project).
export const getRemoteBranches = (url: string, project?: string) =>
  post<RemoteInfo>("/api/remote-branches", project === undefined ? { url } : { url, project });

// The folder a clone of `url` would go to (`path`, else the default one), as the core finds it.
export const getCloneTarget = (url: string, path: string | null) =>
  get<CloneTarget>(`/api/clone-target?${query(path ? { url, path } : { url })}`);

// A clone job of the server: asking for it keeps it alive.
export const startClone = (start: CloneStart) => post<CloneJob>("/api/clones", start);

export const getClone = (id: string) => get<CloneJob>(`/api/clones/${encodeURIComponent(id)}`);

export const cancelClone = (id: string) => post<CloneJob>(`/api/clones/${encodeURIComponent(id)}`, undefined, "DELETE");

// The same as a beacon, which still goes out while the page goes away (tab closed, reloaded).
export const cancelCloneOnLeave = (id: string) =>
  navigator.sendBeacon?.(`/api/clones/${encodeURIComponent(id)}/cancel`);

// The kits a session of the folder `where` can take, one per name.
export const getKits = (where: string | null) =>
  get<KitInfo[]>(where ? `/api/kits?${query({ where })}` : "/api/kits");

// LADO's providers, each one's CLI checked anew.
export const getProviders = () => get<ProviderInfo[]>("/api/providers");

// What the session's head shows besides its settings: its repository, its kits' and its
// provider's versions as installed now; read anew by the server each time.
export const getSessionAbout = (session: string) => get<SessionAbout>(`${sessionPath(session)}/about`);

export type ProjectSummary = components["schemas"]["ProjectSummary"];
export type ProjectInfo = components["schemas"]["ProjectInfo"];
export type ProjectId = components["schemas"]["ProjectId"];
export type VariableChange = components["schemas"]["VariableChange"];

// The Projects section (docs/design/ui.md, Projects): read anew, no feed.
export const listProjects = () => get<ProjectSummary[]>("/api/projects");

const projectPath = (id: string) => `/api/projects/${encodeURIComponent(id)}`;

export const getProject = (id: string) => get<ProjectInfo>(projectPath(id));

export const createProject = (id: string, title: string | null) => post<ProjectInfo>("/api/projects", { id, title });

// Set or clear (null) the project's title, as `lado project rename` does; the project after.
export const renameProject = (id: string, title: string | null) =>
  post<ProjectInfo>(projectPath(id), { title }, "PATCH");

export type ProjectDeletion = components["schemas"]["ProjectDeletion"];

// What deleting the project does: its folder, the unpushed work, the sessions forgotten, the
// names of its variables and secrets; asking changes nothing.
export const getProjectDeletion = (id: string) => get<ProjectDeletion>(`${projectPath(id)}/deletion`);

// Delete the project as `lado project delete --yes` does; no answer but 204.
export const deleteProject = (id: string) => post<void>(projectPath(id), undefined, "DELETE");

export type RepoRemoval = components["schemas"]["RepoRemoval"];

const repoPath = (id: string, name: string) => `${projectPath(id)}/repos/${encodeURIComponent(name)}`;

// A repository of the project from scratch: one empty commit (a clone is a clone job).
export const addProjectRepo = (id: string, name: string) =>
  post<ProjectRepo>(`${projectPath(id)}/repos`, { name });

// What removing the repository does: its folder, the unpushed work and the sessions forgotten.
export const getRepoRemoval = (id: string, name: string) => get<RepoRemoval>(`${repoPath(id, name)}/removal`);

// Remove the repository and forget its sessions; the project after.
export const removeProjectRepo = (id: string, name: string) =>
  post<ProjectInfo>(repoPath(id, name), undefined, "DELETE");

// The id New project offers for a title, or the id as typed, with its folder and the core's
// refusal; asking makes nothing.
export const suggestProjectId = (given: { title: string } | { id: string }) =>
  get<ProjectId>(`/api/project-id?${query(given)}`);

const variablePath = (id: string, kind: "variables" | "secrets", name: string) =>
  `${projectPath(id)}/${kind}/${encodeURIComponent(name)}`;

export const putVariable = (id: string, name: string, value: string) =>
  post<VariableChange>(variablePath(id, "variables", name), { value }, "PUT");

export const deleteVariable = (id: string, name: string) =>
  post<VariableChange>(variablePath(id, "variables", name), undefined, "DELETE");

// A secret's value goes in this request's body only: never in its address, never kept.
export const putSecret = (id: string, name: string, value: string) =>
  post<VariableChange>(variablePath(id, "secrets", name), { value }, "PUT");

export const deleteSecret = (id: string, name: string) =>
  post<VariableChange>(variablePath(id, "secrets", name), undefined, "DELETE");

export type ProjectLaunch = components["schemas"]["ProjectLaunch"];
export type ProjectPlace = components["schemas"]["ProjectPlace"];
export type ProjectRepo = components["schemas"]["ProjectRepo"];

// What New session's Project way shows: the projects, the project and repository chosen
// (those asked, else the last used), and what a start there takes; asking makes nothing.
export const getProjectLaunch = (project: string | null, repo: string | null) => {
  const asked = { ...(project ? { project } : {}), ...(repo ? { repo } : {}) };
  return get<ProjectLaunch>(`/api/project-launch${Object.keys(asked).length ? `?${query(asked)}` : ""}`);
};

export const startSession = (launch: Launch) => post<Started>("/api/sessions", launch);

export const resumeSession = (session: string, resume: Resume) =>
  post<Started>(`${sessionPath(session)}/resume`, resume);

export const getStopPreview = (session: string) => get<StopPreview>(`${sessionPath(session)}/stop-preview`);

export const stopSession = (session: string) => post<Stopped>(`${sessionPath(session)}/stop`);

export const getForgetPreview = (session: string) => get<ForgetPreview>(`${sessionPath(session)}/forget-preview`);

export const forgetSession = (session: string, force: boolean) =>
  post<Forgotten>(`${sessionPath(session)}?${query({ force: String(force) })}`, undefined, "DELETE");

// The Kits page (docs/design/ui.md, Kits): what `lado kits` and `lado marketplaces` do.

export type InstalledKitInfo = components["schemas"]["InstalledKitInfo"];
export type OfferInfo = components["schemas"]["OfferInfo"];
export type MarketplaceInfo = components["schemas"]["MarketplaceInfo"];
export type PlanInfo = components["schemas"]["PlanInfo"];
export type KitContentsInfo = components["schemas"]["KitContentsInfo"];
export type PlanAsk = components["schemas"]["PlanAsk"];
export type InstallKit = components["schemas"]["InstallKit"];
export type KitUsersInfo = components["schemas"]["KitUsersInfo"];
export type OutdatedInfo = components["schemas"]["OutdatedInfo"];
export type MarketplaceUpdate = components["schemas"]["MarketplaceUpdate"];

const kitPath = (name: string) => `/api/kits/${encodeURIComponent(name)}`;
const marketplacePath = (name: string) => `/api/marketplaces/${encodeURIComponent(name)}`;

// The installed kits, then the built-in ones; the kits of the enabled marketplaces; the
// marketplaces. None of them goes to the network.
export const getInstalledKits = () => get<InstalledKitInfo[]>("/api/kits/installed");
export const getAvailableKits = () => get<OfferInfo[]>("/api/kits/available");
export const getMarketplaces = () => get<MarketplaceInfo[]>("/api/marketplaces");

// The sessions that use an installed kit, and what the core says of them.
export const getRemovePreview = (name: string) => get<KitUsersInfo>(`${kitPath(name)}/remove-preview`);

// What an add would do (the network, the git cache); an install of what the plan showed.
export const planKit = (ask: PlanAsk) => post<PlanInfo>("/api/kits/plan", ask);
export const installKit = (given: InstallKit) => post<InstalledKitInfo>("/api/kits/install", given);

export const planKitUpdate = (name: string, tag: string | null) =>
  post<PlanInfo>(`${kitPath(name)}/plan-update`, tag === null ? {} : { tag });
export const updateKit = (name: string, tag: string, commit: string) =>
  post<InstalledKitInfo>(`${kitPath(name)}/update`, { tag, commit });
export const removeKit = (name: string) => post<void>(kitPath(name), undefined, "DELETE");

// Each installed kit against its repository's tags now (the network).
export const checkUpdates = () => post<OutdatedInfo[]>("/api/kits/check-updates");

export const addMarketplace = (name: string, url: string) =>
  post<MarketplaceInfo>("/api/marketplaces", { name, url });
export const setMarketplaceEnabled = (name: string, enabled: boolean) =>
  post<MarketplaceInfo>(marketplacePath(name), { enabled }, "PATCH");
export const removeMarketplace = (name: string) => post<void>(marketplacePath(name), undefined, "DELETE");
// One marketplace, or each enabled one (the network); one that fails says why.
export const updateMarketplaces = (name?: string) =>
  post<MarketplaceUpdate[]>("/api/marketplaces/update", name === undefined ? {} : { name });

// Why the server refuses the event stream at `path`: an ApiError, or nothing when it would
// open now. Reads only the answer's head; an open stream is closed at once.
export async function probeStream(path: string): Promise<void> {
  const abort = new AbortController();
  const answer = await fetch(path, { credentials: "same-origin", signal: abort.signal });
  if (!answer.ok) throw await refused(answer);
  abort.abort();
}
