// The New session window (docs/design/ui.md, Launch and session control): opened from the
// rail's New session, the session list's "+", and in its Resume mode from a stopped session's
// Resume. Top to bottom: Where (LaunchWhere.tsx), Task, Team (LaunchTeam.tsx), and a footer
// that never scrolls, which says what is missing while its button is off. What a folder is,
// which kits and providers there are and whether a name is taken all come from the server;
// the window decides nothing the core decides.
import { createContext, useContext, useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { useNavigate } from "react-router";

import {
  ApiError,
  getCloneTarget,
  getFolder,
  getKits,
  getLimits,
  getProjectLaunch,
  getProviders,
  getRecentFolders,
  getWorkspace,
  getRemoteBranches,
  getScratchTarget,
  resumeSession,
  startSession,
  type CloneJob,
  type CloneRefused,
  type CloneTarget,
  type FolderInfo,
  type Launch,
  type Limits,
  type ModelRefusal,
  type ProjectLaunch,
  type ProjectPlace,
  type ProviderSuggestion,
  type RecentFolder,
  type Refused,
  type RemoteInfo,
  type Resume,
  type ScratchTarget,
  type SessionInfo,
  type Started,
} from "./api";
import { closedBy, looks, resumeAttempt } from "./attempts";
import { since } from "./ChatText";
import { useCloneJob } from "./cloneJob";
import { InfoTip } from "./InfoTip";
import { useLaunchModel, type Choice } from "./LaunchModel";
import { ProjectField } from "./LaunchProject";
import { LaunchSetup } from "./LaunchSetup";
import { cannotStart, DEFAULT_MODE, LaunchTeam, modeWords } from "./LaunchTeam";
import {
  BranchField,
  FolderHint,
  FolderNotes,
  FolderPathField,
  lastPart,
  PlaceBox,
  PlaceIcon,
  ScratchNameField,
  TargetNote,
  UrlField,
  withSlash,
  type Shown,
  type Way,
} from "./LaunchWhere";
import { useLive, useLiveStore, useLocked } from "./live";
import { useModal } from "./modal";
import { agentClisPath, projectPath, sessionPath } from "./paths";
import { ActionProblem, Waits } from "./waitingParts";

export { FolderHint };

// How long the window waits after a keystroke before it asks the server about the folder.
export const DEBOUNCE = 200;
// The same before it asks for the check of a typed model, which may run the CLI's list.
export const MODEL_DEBOUNCE = 300;
// The same before it asks a remote for its branches, which goes to the network.
export const BRANCHES_DEBOUNCE = 500;
// Up to this many branches the Branch field is a list; more, a field that filters them.
export const BRANCH_LIST = 30;
// The target states a clone may start in (lado.clone.CAN_CLONE).
const CAN_CLONE = new Set<CloneTarget["state"]>(["new", "empty"]);
// The folder states a fresh start may go on in (lado.scratch.CAN_START).
const CAN_START = new Set<ScratchTarget["state"]>(["new", "empty"]);

const DEFAULT_KIT = "default";

const TASK_ABOUT = "The team gets this as its first message and answers in the chat. You can leave it empty.";
const MESSAGE_ABOUT = "The team gets this as a message once it resumes, and answers in the chat. You can leave it empty.";
const RESUME_ABOUT = "The team continues where it stopped: its chat, tasks and work stay.";

// A session of these statuses can be resumed; a running one only opened.
const RESUMABLE = new Set<SessionInfo["status"]>(["stopped", "tmux_gone"]);

// A new session's window opens on a project (and its repository; the project's page) or a
// folder (Resume's Start a new session instead), else on the last place.
export type LaunchMode =
  | { kind: "new"; project?: string; repo?: string; path?: string }
  | { kind: "resume"; session: SessionInfo };

const LaunchContext = createContext<(mode?: LaunchMode) => void>(() => {});

// Opens the New session window, or its Resume mode for a session.
export const useLaunch = () => useContext(LaunchContext);

// What a start or resume said, for the session's page to show (its problems until closed).
export type StartedState = { started: Started };

// What the New session window keeps when it closes without a start, until a start or a
// reload of the page.
type Draft = {
  source: Way;
  otherFolder: boolean;
  projectPick: boolean;
  path: string;
  projectAsk: { project: string | null; repo: string | null };
  scratchText: string;
  scratchInto: string | null;
  url: string;
  into: string | null;
  prompt: string;
  name: string | null;
  kits: string[];
  provider: string | null;
  permissionMode: string;
  without: string;
  touched: string[];
  teamOpen: boolean;
  model: { cli: string; choice: Choice } | null; // the Model field's choice, for its agent CLI
};

export function LaunchProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<LaunchMode | null>(null);
  const draft = useRef<Draft | null>(null);
  const shown = useRef(mode);
  shown.current = mode;
  return (
    <LaunchContext.Provider value={(next = { kind: "new" }) => setMode(next)}>
      {children}
      {mode && (
        <LaunchDialog
          key={
            mode.kind === "resume"
              ? `resume:${mode.session.name}`
              : `new:${mode.project ?? ""}:${mode.repo ?? ""}:${mode.path ?? ""}`
          }
          mode={mode}
          draft={mode.kind === "new" && !mode.project && !mode.path ? draft.current : null}
          onDraft={(kept) => {
            draft.current = kept;
          }}
          onMode={setMode}
          onClose={() => setMode(null)}
          resumes={(name) => shown.current?.kind === "resume" && shown.current.session.name === name}
        />
      )}
    </LaunchContext.Provider>
  );
}

// A value as it was once it stopped changing for `ms`: one request per pause in typing.
export function useDebounced<T>(value: T, ms = DEBOUNCE): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

// null: asking; an error's `detail` is the server's (a CloneRefused for a clone)
export type Asked<T> = { value: T } | { error: string; detail?: unknown } | null;

// The server's answer to `ask(key)`, asked again when `key` changes; nothing for a null key.
export function useAsked<T>(key: string | null, ask: (key: string) => Promise<T>): Asked<T> {
  const [asked, setAsked] = useState<{ key: string; answer: Asked<T> } | null>(null);
  useEffect(() => {
    if (key === null) return;
    let current = true;
    ask(key).then(
      (value) => current && setAsked({ key, answer: { value } }),
      (error: unknown) =>
        current &&
        setAsked({
          key,
          answer: { error: messageOf(error), detail: error instanceof ApiError ? error.detail : undefined },
        }),
    );
    return () => {
      current = false;
    };
    // `ask` is one of the API's functions: the same for the window's life.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return asked !== null && asked.key === key ? asked.answer : null;
}

function useOnce<T>(ask: () => Promise<T>, skip = false): Asked<T> {
  return useAsked(skip ? null : "", () => ask());
}

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

export const valueOf = <T,>(asked: Asked<T>): T | null => (asked !== null && "value" in asked ? asked.value : null);

const sameFolder = (path: string, folder: string | null) => folder !== null && withSlash(path) === withSlash(folder);

const splitWithout = (text: string) => text.split(/[\s,]+/).filter(Boolean);

const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((one, i) => one === b[i]);

// A refusal's detail as a CloneRefused, when it is one (its hint shown with Copy).
export const cloneRefused = (detail: unknown): CloneRefused | null =>
  detail !== null && typeof detail === "object" && "kind" in detail ? (detail as CloneRefused) : null;

const elapsed = (seconds: number) => {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
};

// The branch a clone takes unless the human picks one: the remote's default, else main,
// else master, else the first.
export const defaultBranch = (remote: RemoteInfo) =>
  remote.default ?? ["main", "master"].find((one) => remote.branches.includes(one)) ?? remote.branches[0];

// The name after a taken one, for a start a race refused: "webapp-2" after "webapp".
const nextName = (name: string) => {
  const numbered = /^(.*)-(\d+)$/.exec(name);
  return numbered ? `${numbered[1]}-${Number(numbered[2]) + 1}` : `${name}-2`;
};

// A missing item of the footer's "To start:", and the field it leads to.
type Missing = { text: string; focus: () => void };

function LaunchDialog({
  mode,
  draft,
  onDraft,
  onMode,
  onClose,
  resumes,
}: {
  mode: LaunchMode;
  draft: Draft | null; // what the window held when it last closed without a start
  onDraft: (draft: Draft | null) => void;
  onMode: (mode: LaunchMode) => void;
  onClose: () => void;
  resumes: (session: string) => boolean; // the window stands now in Resume mode for it
}) {
  const resuming = mode.kind === "resume" ? mode.session : null;
  const asksProject = mode.kind === "new" ? (mode.project ?? null) : null;
  const asksPath = mode.kind === "new" ? (mode.path ?? null) : null;
  const dialog = useRef<HTMLDialogElement>(null);
  const navigate = useNavigate();
  const live = useLive();
  const store = useLiveStore();
  const attempt = resumeAttempt(resuming?.name ?? "");
  const waiting = useLocked(attempt) && resuming !== null; // New session's start does not wait
  const ids = useId();
  const whereRef = useRef<HTMLInputElement>(null);
  const pathRef = useRef<HTMLInputElement>(null);
  const urlRef = useRef<HTMLInputElement>(null);
  const scratchRef = useRef<HTMLInputElement>(null);
  const taskRef = useRef<HTMLTextAreaElement>(null);
  const refusedRef = useRef<HTMLDivElement>(null);
  const actionRef = useRef<HTMLButtonElement>(null);
  const teamRefs = {
    name: useRef<HTMLInputElement>(null),
    agent: useRef<HTMLSelectElement>(null),
    kits: useRef<HTMLSelectElement>(null),
  };

  const [path, setPath] = useState(resuming?.repo ?? draft?.path ?? asksPath ?? "");
  const [name, setName] = useState<string | null>(resuming?.name ?? draft?.name ?? null); // null: the default
  const [kits, setKits] = useState<string[]>(resuming?.kits ?? draft?.kits ?? [DEFAULT_KIT]);
  // null: none chosen; a new session's comes from the place's suggestion (the core's rule)
  const [provider, setProvider] = useState<string | null>(resuming?.provider ?? draft?.provider ?? null);
  const [suggested, setSuggested] = useState<ProviderSuggestion["reason"] | null>(null);
  const [permissionMode, setPermissionMode] = useState(
    resuming?.permission_mode ?? draft?.permissionMode ?? DEFAULT_MODE,
  );
  const [without, setWithout] = useState(resuming?.without.join(", ") ?? draft?.without ?? "");
  const [teamOpen, setTeamOpen] = useState(draft?.teamOpen ?? false);
  const [prompt, setPrompt] = useState(draft?.prompt ?? ""); // the task: the human's first message
  const [touched, setTouched] = useState<Set<string>>(new Set(draft?.touched ?? []));
  const [fromLast, setFromLast] = useState(false);
  const [modeNote, setModeNote] = useState<string | null>(null);
  // What runs now, for the button's word: a start, a set-up, a resume.
  const [busy, setBusyKind] = useState<"start" | "setup" | "resume" | null>(null);
  const setBusy = (on: boolean) => setBusyKind(on ? "start" : null);
  const [refused, setRefused] = useState<ApiError | null>(null);
  // Where: the way and its fields; a folder's path, a project and repository asked of the
  // server (null: its choice), a fresh start's name and folder, a clone's URL and folder.
  const [source, setSourceState] = useState<Way>(asksProject ? "project" : (draft?.source ?? "folder"));
  const [otherFolder, setOtherFolder] = useState(draft?.otherFolder ?? false);
  const [projectPick, setProjectPick] = useState(asksProject !== null || (draft?.projectPick ?? false));
  // The window opens on the last place once the recent places answer, unless it was told
  // where (the project's page, Start a new session instead) or kept a draft.
  const placeTouched = useRef(asksProject !== null || asksPath !== null || draft !== null);
  const [projectAsk, setProjectAsk] = useState<{ project: string | null; repo: string | null }>(
    asksProject !== null
      ? { project: asksProject, repo: (mode.kind === "new" && mode.repo) || null }
      : (draft?.projectAsk ?? { project: null, repo: null }),
  );
  const setSource = (next: Way) => {
    placeTouched.current = true;
    setSourceState(next);
  };
  const [scratchText, setScratchText] = useState(draft?.scratchText ?? "");
  const [scratchInto, setScratchInto] = useState<string | null>(draft?.scratchInto ?? null);
  const [url, setUrl] = useState(draft?.url ?? "");
  const [into, setInto] = useState<string | null>(draft?.into ?? null);
  const [picked, setPicked] = useState<{ url: string; branch: string } | null>(null);
  const [include, setInclude] = useState<string[]>([]); // the set-up's left-out files ticked in
  const [checkTurn, setCheckTurn] = useState(0); // Check again of the set-up's author
  const clone = useCloneJob(); // its beacon cancels the clone of a page that goes away
  const job = clone.job;
  const [cloneEnd, setCloneEnd] = useState<{ note: string } | { refused: CloneRefused } | null>(null);
  const branchesAsked = useRef(new Map<string, Promise<RemoteInfo>>());

  useModal(dialog);

  const cloning = source === "url";
  const scratching = source === "scratch";
  const projecting = source === "project";
  const projectAsked = useAsked(projecting && !resuming ? JSON.stringify(projectAsk) : null, (key) => {
    const { project, repo } = JSON.parse(key) as typeof projectAsk;
    return getProjectLaunch(project, repo);
  });
  // What a start takes: only the answer to what is asked now.
  const inProject = valueOf(projectAsked);
  const projectRepo = inProject?.repos.find((one) => one.name === inProject.repo) ?? null;
  // What the field shows: while a new choice is asked, the last answer with the choice in
  // it, so the field stays (its select and list, their focus) and Start waits.
  const [lastProject, setLastProject] = useState<ProjectLaunch | null>(null);
  useEffect(() => {
    if (inProject) setLastProject(inProject);
  }, [inProject]);
  const shownProject =
    inProject ??
    (lastProject && {
      ...lastProject,
      project: projectAsk.project ?? lastProject.project,
      repo:
        projectAsk.project === lastProject.project && projectAsk.repo !== null ? projectAsk.repo : lastProject.repo,
    });
  // The button names the project the session goes to: another project's session gets
  // another client's keys.
  const chosenProject = shownProject?.projects.find((one) => one.id === shownProject.project) ?? null;
  const projectTitle = projecting && chosenProject ? (chosenProject.title ?? chosenProject.id) : null;
  const typedText = scratchText.trim();
  const typedScratchInto = (scratchInto ?? "").trim();
  const settledText = useDebounced(typedText);
  const settledScratchInto = useDebounced(typedScratchInto);
  // Only the latest request's answer: useAsked shows the answer of the key asked last.
  const scratchAsked = useAsked(
    scratching && (settledText || settledScratchInto) ? JSON.stringify([settledText, settledScratchInto]) : null,
    (key) => {
      const [text, where] = JSON.parse(key) as [string, string];
      return getScratchTarget(text, where || null);
    },
  );
  const fresh =
    settledText === typedText && settledScratchInto === typedScratchInto ? valueOf(scratchAsked) : null;
  const typedUrl = url.trim();
  const typedInto = (into ?? "").trim();
  const settledUrl = useDebounced(typedUrl);
  const settledInto = useDebounced(typedInto);
  const targetAsked = useAsked(cloning && settledUrl ? JSON.stringify([settledUrl, settledInto]) : null, (key) => {
    const [asked, where] = JSON.parse(key) as [string, string];
    return getCloneTarget(asked, where || null);
  });
  const target = settledUrl === typedUrl && settledInto === typedInto ? valueOf(targetAsked) : null;
  const branchesUrl = useDebounced(typedUrl, BRANCHES_DEBOUNCE);
  // Each URL's branches are asked once in the window's life.
  const remoteAsked = useAsked(cloning && branchesUrl ? branchesUrl : null, (asked) => {
    const known = branchesAsked.current.get(asked);
    if (known) return known;
    const listing = getRemoteBranches(asked);
    listing.catch(() => branchesAsked.current.delete(asked)); // asked again after a failure
    branchesAsked.current.set(asked, listing);
    return listing;
  });
  const remote = branchesUrl === typedUrl ? valueOf(remoteAsked) : null;
  const branch = remote
    ? picked?.url === typedUrl && remote.branches.includes(picked.branch)
      ? picked.branch
      : defaultBranch(remote)
    : null;

  const workspace = valueOf(useOnce(getWorkspace, resuming !== null)) ?? null;
  // The workspace itself holds the repositories, it is none: no check, as for an
  // empty field (its "not inside a git repository" would offer `git init` over them all).
  const toCheck = (where: string) =>
    where !== "" && !sameFolder(where, workspace?.path ?? null) ? where : null;
  // In the workspace, which the first clone or fresh start makes; nothing before it is known.
  const inWorkspace = (rest: string) => (workspace ? `${withSlash(workspace.path)}${rest}` : "");
  const settled = useDebounced(path.trim());
  const checkKey = resuming ? null : toCheck(settled);
  const checked = useAsked(checkKey === null ? null : JSON.stringify([checkKey, checkTurn]), (key) =>
    getFolder((JSON.parse(key) as [string, number])[0]),
  );
  const folder = valueOf(checked);
  // The answer to what the field holds now: useAsked gives only the answer of the key asked,
  // and the answer's own path is no match for the text (the server expands `~`).
  const current = folder !== null && settled === path.trim() ? folder : null;
  // A plain folder checked again (Check again, a refused set-up): its last answer stays in
  // sight, the panel counting or its Check again "Checking…", until the new one comes; a
  // failed ask shows its error instead.
  const [lastPlain, setLastPlain] = useState<{ key: string; info: FolderInfo } | null>(null);
  useEffect(() => {
    if (current && checkKey !== null) setLastPlain(current.setup ? { key: checkKey, info: current } : null);
  }, [current, checkKey]);
  const rechecking =
    !resuming &&
    source === "folder" &&
    checked === null &&
    checkKey !== null &&
    settled === path.trim() &&
    lastPlain?.key === checkKey;
  const shownFolder = current ?? (rechecking ? lastPlain!.info : null);
  // Check again answered with the author known: its button went, the focus goes on to Task.
  const wasRechecking = useRef(false);
  useEffect(() => {
    if (wasRechecking.current && !rechecking && document.activeElement === document.body) taskRef.current?.focus();
    wasRechecking.current = rechecking;
  }, [rechecking]);
  const recentAsked = valueOf(useOnce(getRecentFolders, resuming !== null));
  const recent = recentAsked ?? [];
  // The first answer of the recent places sets the window on the last place, or on New empty
  // folder without one; the focus goes where the human types next.
  const [opened, setOpened] = useState<"task" | "scratch" | null>(
    draft !== null || asksProject !== null || asksPath !== null ? "task" : null,
  );
  useEffect(() => {
    if (recentAsked === null || placeTouched.current) return;
    placeTouched.current = true; // decided once
    const last = recentAsked[0];
    if (!last) {
      setSourceState("scratch");
      setOpened("scratch");
    } else if (last.project?.repo) {
      setSourceState("project");
      setProjectPick(false);
      setProjectAsk({ project: last.project.id, repo: last.project.repo });
      setOpened("task");
    } else {
      setSourceState("folder");
      setOtherFolder(false);
      setPath(last.path);
      setOpened("task");
    }
  }, [recentAsked]);
  useEffect(() => {
    if (opened === null || resuming) return;
    (opened === "scratch" ? scratchRef : taskRef).current?.focus();
  }, [opened, resuming]);
  useEffect(() => {
    if (resuming) taskRef.current?.focus();
  }, [resuming]);

  // In Project the repository's git root (links resolved), as a session's folder is given.
  const root = resuming?.repo ?? (scratching ? null : projecting ? inProject?.root : folder?.root) ?? null;
  const kitList = useAsked(root ?? "", (where) => getKits(where || null));
  // Asked again for each project chosen: a project's secrets may log a CLI in. A resumed
  // session's are its project's; the other ways' none.
  const loginsOf = resuming ? (resuming.project ?? "") : projecting ? (inProject?.project ?? null) : "";
  const providerList = useAsked(loginsOf, (project) => getProviders(project || null));
  const providers = valueOf(providerList);
  // Without the limits the server checks the task's length alone.
  const maxMessage = valueOf(useOnce<Limits>(getLimits))?.max_message ?? null;
  const promptText = prompt.trim();
  const promptOver = maxMessage !== null && promptText.length > maxMessage;
  const withPrompt = promptText ? { prompt: promptText } : {};

  // A new session's suggestion of a CLI without its login is not taken (held): the field
  // stays at "choose…" and says why. A resume keeps its session's CLI chosen, and is refused
  // without its login as a new session is (lado.logins): another CLI can be chosen. A CLI
  // that starts on a saved model of a server without it is offered, for those models only.
  const inList = providers?.find((one) => one.name === provider) ?? null;
  const held = !resuming && !touched.has("provider") && inList !== null && cannotStart(inList);
  const chosenProvider = held ? null : provider;
  const providerInfo = held ? null : inList;
  const noLogin = inList && cannotStart(inList) ? inList : null;
  const serverOnly = providerInfo?.installed && providerInfo.starts_on_server ? providerInfo : null;
  const canStart = providerInfo?.installed === true && !cannotStart(providerInfo);
  // A provider the session cannot run: Team opens on its refusal.
  const providerRefused =
    providers !== null && (noLogin?.installed === true || (chosenProvider !== null && !providerInfo?.installed));
  useEffect(() => {
    if (providerRefused) setTeamOpen(true);
  }, [providerRefused]);

  const modelRefusal = refused?.status === 409 && isModelRefusal(refused.detail) ? refused.detail : null;
  const model = useLaunchModel({
    cli: providerInfo ?? null,
    project: loginsOf,
    resuming,
    busy: busy !== null,
    refusal: modelRefusal,
    onClearRefusal: () => setRefused((now) => (now?.status === 409 && isModelRefusal(now.detail) ? null : now)),
    onShow: () => setTeamOpen(true),
    onLogin: () => providerInfo && leave(agentClisPath(providerInfo.name)),
    draft: draft?.model ?? null,
  });
  const modelReady = !model.blocked;

  // Kits and mode of a new session come from the folder's last session; in Project, from
  // the repository's last session in the project.
  const last = resuming
    ? null
    : projecting
      ? (inProject?.last ?? null)
      : (recent.find((one) => one.path === folder?.root)?.session ?? null);
  useEffect(() => {
    if (resuming || (folder === null && source === "folder") || (inProject === null && projecting)) return;
    // A clone's or a fresh start's folder has no last session: LADO's defaults, not a
    // folder's typed before.
    const from = source === "folder" || projecting ? last : null;
    if (!touched.has("kits")) setKits(from?.kits ?? [DEFAULT_KIT]);
    if (!touched.has("mode")) setPermissionMode(from?.permission_mode ?? DEFAULT_MODE);
    setFromLast(from !== null);
    // Again only when the folder's last session is another one, or the source changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [last?.name, folder?.root, projectRepo?.path, source]);

  // No provider is the default: the place's suggestion (a clone's or a fresh start's
  // folder's, a project's repository's), with its reason, or none.
  const suggesting = cloning ? target : scratching ? fresh : projecting ? inProject : folder;
  const suggestingPath = suggesting && "path" in suggesting ? suggesting.path : (projectRepo?.path ?? null);
  useEffect(() => {
    if (resuming || suggesting === null || touched.has("provider")) return;
    setProvider(suggesting.provider?.name ?? null);
    setSuggested(suggesting.provider?.reason ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestingPath, suggesting?.provider?.name, suggesting?.provider?.reason, source]);

  const touch = (field: string) => setTouched((before) => new Set(before).add(field));

  // The focus a pick or a refusal moves, once the render that shows its field is done: not
  // a frame later, when the human may type in another field already.
  const [toFocus, setToFocus] = useState<{ run: () => void } | null>(null);
  const focusNext = (run: () => void) => setToFocus({ run });
  useEffect(() => {
    toFocus?.run();
  }, [toFocus]);

  const named = cloning ? target : projecting ? shownProject : current;
  // The session's name: the human's, else the place's free one (its default when free).
  const shownName = scratching ? (fresh?.name ?? "") : (name ?? named?.free_name ?? named?.default_name ?? "");
  const resumable = (sessionName: string) => {
    const loaded = live.sessions;
    return loaded && "sessions" in loaded ? loaded.sessions.find((one) => one.name === sessionName) : undefined;
  };
  // A stopped session of the place's default name: the line under Where names it, to say why
  // the new session takes the free name; it is resumed from its page or the session list. In a
  // project only one of this project, as the core resumes none of another.
  const stoppedSession =
    !resuming && !cloning && !scratching && named?.name_state === "stopped_here" && named.default_name
      ? resumable(named.default_name)
      : undefined;
  const stopped =
    stoppedSession && RESUMABLE.has(stoppedSession.status) && (!projecting || stoppedSession.project === inProject?.project)
      ? stoppedSession
      : null;

  const chooseProvider = (next: string) => {
    touch("provider");
    setProvider(next);
    setSuggested(null);
    const info = providers?.find((one) => one.name === next);
    const supported = info?.permission_modes ?? [];
    if (permissionMode !== DEFAULT_MODE && !supported.includes(permissionMode)) {
      setModeNote(`${info?.title ?? next} has no such mode: set to the default`);
      setPermissionMode(DEFAULT_MODE);
    } else {
      setModeNote(null);
    }
  };

  // A plain folder of files the start sets up first (lado.setup).
  const setup = !resuming && source === "folder" && current && !current.ok ? (current.setup ?? null) : null;
  const settingUp = setup !== null;
  const setupReady = setup !== null && setup.refusal === null && setup.author === null;

  // What each way needs beyond the team; the team's part holds in every way.
  const teamReady = canStart && modelReady && kits.length > 0 && !promptOver;
  const folderReady = (resuming !== null || (current?.ok ?? false) || setupReady) && teamReady;
  const cloneReady =
    teamReady && remote !== null && target !== null && CAN_CLONE.has(target.state) && shownName !== "";
  const scratchReady =
    teamReady &&
    fresh !== null &&
    fresh.path !== null &&
    fresh.name !== null &&
    CAN_START.has(fresh.state) &&
    fresh.author === null &&
    fresh.name_state === "free";
  const projectReady = teamReady && projectRepo !== null && shownName !== "";
  // Use this clone only turns Where to the clone that is there.
  const useClone = cloning && target?.state === "same_repo";
  const ready = useClone || (cloning ? cloneReady : scratching ? scratchReady : projecting ? projectReady : folderReady);

  // A new session in `where`, as the window's fields say; from scratch, its folder is made
  // a repository first, and the session takes the name and title of the name typed.
  const startIn = (where: Launch["where"]) => {
    const off = splitWithout(without);
    const scratchNames =
      where.kind === "scratch" ? { name: fresh?.name, ...(fresh?.title ? { title: fresh.title } : {}) } : null;
    return startSession({
      where,
      ...(scratchNames ?? (shownName ? { name: shownName } : {})),
      kits,
      ...(chosenProvider !== null ? { provider: chosenProvider } : {}),
      ...(permissionMode !== DEFAULT_MODE ? { permission_mode: permissionMode } : {}),
      ...(off.length ? { without: off } : {}),
      ...(model.send !== undefined ? { model: model.send } : {}),
      ...withPrompt,
    });
  };

  // Closing without a start keeps the draft; a start clears it.
  const close = () => {
    if (!resuming) {
      onDraft({
        source,
        otherFolder,
        projectPick,
        path,
        projectAsk,
        scratchText,
        scratchInto,
        url,
        into,
        prompt,
        name,
        kits,
        provider,
        permissionMode,
        without,
        touched: [...touched],
        teamOpen,
        model: model.kept,
      });
    }
    onClose();
  };

  const openSession = (started: Started) => {
    onDraft(null);
    onClose();
    const state: StartedState = { started };
    navigate(sessionPath(started.session.name, "activity"), { state });
  };

  const toFolder = (where: string) => {
    setSource("folder");
    setOtherFolder(false);
    setPath(where);
  };

  // Start from scratch here: the folder checked becomes New empty folder's target, its
  // last segment the folder's name.
  const toScratch = (where: string) => {
    setSource("scratch");
    setScratchInto(where);
    setScratchText(lastPart(where));
    setRefused(null);
  };

  // Folder's refusal inside a project: the project's repository, or the project's page.
  const toProject = (place: ProjectPlace) => {
    if (place.repo === null) {
      leave(projectPath(place.id));
      return;
    }
    setSource("project");
    setProjectPick(false);
    setProjectAsk({ project: place.id, repo: place.repo });
    setRefused(null);
  };

  const leave = (to: string) => {
    onClose();
    navigate(to);
  };

  // A refused request: Team opens on a refusal of one of its fields, the focus goes to the
  // field to fix, else to the refusal.
  const refuse = (error: unknown) => {
    const given = error instanceof ApiError ? error : new ApiError(0, String(error));
    setRefused(given);
    const taken = given.status === 409 && !isModelRefusal(given.detail);
    const switchOff = given.status === 400 && hasSwitchOff(given.detail);
    if (taken || switchOff || isModelRefusal(given.detail)) setTeamOpen(true);
    focusNext(() => {
      if (taken) teamRefs.name.current?.focus();
      else if (isModelRefusal(given.detail)) model.focus();
      else refusedRef.current?.focus();
    });
  };

  // Make the folder a repository and start there; a start refused after the repository
  // was made leaves the window on the folder with the refusal, as after a clone.
  const createAndStart = async () => {
    if (fresh?.path == null) return;
    const where = fresh.path;
    setBusy(true);
    setRefused(null);
    try {
      openSession(await startIn({ kind: "scratch", path: where }));
    } catch (error) {
      const given = error instanceof ApiError ? error : new ApiError(0, String(error));
      if (given.status === 400 || given.status === 409) {
        const made = await getFolder(where).catch(() => null);
        if (made?.ok) toFolder(where);
      }
      setBusy(false);
      refuse(given);
    }
  };

  // Set the plain folder up and start there; a start refused after the set-up leaves the
  // window on the folder, now a repository, with the refusal.
  const setUpAndStart = async () => {
    if (current === null) return;
    const where = current.path;
    setBusyKind("setup");
    setRefused(null);
    try {
      // Only what this preview leaves out: a tick of an earlier one may name a file gone.
      const left = new Set(current.setup?.left_out.map((one) => one.path) ?? []);
      openSession(await startIn({ kind: "setup", path: where, include: include.filter((one) => left.has(one)) }));
    } catch (error) {
      setCheckTurn((turn) => turn + 1); // the folder may be a repository now
      setBusy(false);
      refuse(error);
    }
  };

  // Clone, then start in the clone as for a folder; a start refused after the clone leaves
  // the window on the clone's folder with the refusal.
  const cloneAndStart = async () => {
    if (target === null || branch === null) return;
    setBusy(true);
    setRefused(null);
    setCloneEnd(null);
    const failed = (error: unknown) => {
      const given = error instanceof ApiError ? error : new ApiError(0, String(error));
      const why = cloneRefused(given.detail);
      setCloneEnd({ refused: why ?? { message: given.message, kind: "refused", hint: null } });
      setBusy(false);
    };
    const asked = typedUrl; // its field is off while the clone runs
    // A job the server dropped (clone.KEPT) ended while this window did not ask: the clone
    // is there when the folder is now a clone of the URL.
    const isThere = async (lost: CloneJob) => (await getCloneTarget(asked, lost.path)).state === "same_repo";
    let end;
    try {
      end = await clone.run({ url: asked, path: target.path, branch }, isThere);
    } catch (error) {
      failed(error);
      return;
    }
    if ("ended" in end) {
      if (end.ended === "left") return;
      if (end.ended === "gone") {
        failed(end.error); // the job's end is unknown
      } else if (end.ended === "away") {
        toFolder(end.job.path); // offered as a folder
        setCloneEnd({ note: `the clone ended while this window was away; it is in ${end.job.path}` });
        setBusy(false);
      } else {
        setCloneEnd(end.job.error ? { refused: end.job.error } : { note: "the clone was cancelled" });
        setBusy(false);
      }
      return;
    }
    const running = end.done;
    if (end.late) {
      // Cancel clone came too late: the clone is there, and it is offered as a folder.
      toFolder(running.path);
      setCloneEnd({ note: `the clone ended before Cancel clone; it is in ${running.path}` });
      setBusy(false);
      return;
    }
    try {
      openSession(await startIn({ kind: "folder", path: running.path }));
    } catch (error) {
      toFolder(running.path);
      setBusy(false);
      refuse(error);
    }
  };

  // The Team fields changed from those `session` has, and the task, for a resume.
  const changedFrom = (session: SessionInfo): Resume => {
    const off = splitWithout(without);
    const changed: Resume = {};
    if (!sameList(kits, session.kits)) changed.kits = kits;
    if (chosenProvider !== null && chosenProvider !== session.provider) changed.provider = chosenProvider;
    if (permissionMode !== (session.permission_mode ?? DEFAULT_MODE)) changed.permission_mode = permissionMode;
    if (!sameList(off, session.without)) changed.without = off;
    if (model.send !== undefined) changed.model = model.send;
    return { ...changed, ...withPrompt };
  };

  // The Resume window's resume, kept when it gets no answer. Reached by what LADO reads there
  // is no answer to show on the session's page; with no window open for it the human went
  // elsewhere, and stays there. The window may be a later one than this.
  const resume = async (session: SessionInfo, given: Resume) => {
    const got: { started?: Started } = {};
    store.attempts.clear(attempt);
    const answered = await store.attempts.send(attempt, {
      what: "Resume",
      repeat: async () => {
        got.started = await resumeSession(session.name, given);
      },
      look: looks.resume(session.name),
      closed: closedBy.resume,
      reached: () => {
        if (!resumes(session.name)) return;
        if (got.started) openSession(got.started);
        else {
          onClose();
          navigate(sessionPath(session.name, "activity"));
        }
      },
    });
    if (answered) openSession(got.started!);
    else setBusy(false);
  };

  const submit = async () => {
    setBusyKind(resuming ? "resume" : "start");
    setRefused(null);
    try {
      if (resuming) {
        await resume(resuming, changedFrom(resuming));
        return;
      }
      openSession(
        await startIn(
          projecting && inProject?.project && projectRepo
            ? { kind: "project", project: inProject.project, repo: projectRepo.name }
            : { kind: "folder", path: path.trim() },
        ),
      );
    } catch (error) {
      setBusy(false);
      refuse(error);
    }
  };

  // The way's main action.
  const start = () => {
    if (busy !== null || waiting || !ready) return;
    if (cloning) {
      if (target?.state === "same_repo") toFolder(target.path);
      else void cloneAndStart();
    } else if (scratching) void createAndStart();
    else if (settingUp) void setUpAndStart();
    else void submit();
  };

  const title = resuming ? "Resume session" : "New session";
  const taken = refused?.status === 409 && modelRefusal === null ? refused : null;
  const detail = refused?.status === 400 ? refused.detail : null;
  const switchOff = hasSwitchOff(detail) ? (detail as Refused).switch_off : [];

  // What the closed Where shows.
  const placeName = (where: string) => lastPart(where);
  const shown: Shown = cloning
    ? { icon: "link", name: "Clone from URL" }
    : scratching
      ? { icon: "plus", name: "New empty folder", path: scratchInto }
      : projecting
        ? projectPick || !projectRepo
          ? { icon: "project", name: "Project" }
          : { icon: "project", name: projectRepo.name, badge: projectTitle }
        : path.trim()
          ? { icon: "folder", name: placeName(path.trim()), path: path.trim() }
          : otherFolder
            ? { icon: "open", name: "Other folder" }
            : { icon: "folder", name: recentAsked === null ? "…" : "Choose a place" };

  // The footer's buttons: the way's start (or the clone's own), and Resume beside it.
  const placeWord = cloning
    ? target
      ? lastPart(target.path)
      : null
    : projecting
      ? projectTitle
      : path.trim()
        ? placeName(path.trim())
        : null;
  const startLabel = resuming
    ? `Resume ${resuming.name}`
    : cloning
      ? target?.state === "same_repo"
        ? "Use this clone"
        : placeWord
          ? `Clone and start in ${placeWord}`
          : "Clone and start"
      : scratching
        ? "Create and start"
        : settingUp
          ? `Set up and start in ${placeWord}`
          : stopped
            ? projecting
              ? `Start new session in ${projectTitle}`
              : `Start new session ${shownName}`
            : placeWord
              ? `Start in ${placeWord}`
              : "Start";
  const busyLabel = { start: job ? "Cloning…" : "Starting…", setup: "Setting up…", resume: "Resuming…" };

  // What keeps the start off, in the footer's words, each leading to its field.
  const openTeam = (field: RefObject<HTMLElement | null>) => () => {
    setTeamOpen(true);
    focusNext(() => field.current?.focus());
  };
  const missing: Missing[] = [];
  if (!resuming) {
    const toWhere = () => (whereRef.current ?? pathRef.current)?.focus();
    if (scratching) {
      if (!fresh?.name || (fresh.state !== null && !CAN_START.has(fresh.state)) || fresh.name_state !== "free")
        missing.push({ text: "name the folder", focus: () => scratchRef.current?.focus() });
      if (fresh?.author) missing.push({ text: "tell git who you are", focus: () => scratchRef.current?.focus() });
    } else if (cloning) {
      if (remote === null || target === null || (!CAN_CLONE.has(target.state) && target.state !== "same_repo"))
        missing.push({ text: "choose a place", focus: () => urlRef.current?.focus() });
    } else if (projecting) {
      if (projectRepo === null) missing.push({ text: "choose a place", focus: toWhere });
    } else if (rechecking) {
      missing.push({ text: "wait for the count", focus: toWhere });
    } else if (current?.setup) {
      const panel = () => document.getElementById(notesId)?.querySelector<HTMLElement>("button")?.focus();
      const refusal = current.setup.refusal;
      if (refusal) {
        const smaller = refusal.kind === "home" || refusal.kind === "too_big";
        missing.push({ text: smaller ? "choose a smaller folder" : "choose another folder", focus: toWhere });
      } else if (current.setup.author) missing.push({ text: "tell git who you are", focus: panel });
    } else if (!(current?.ok ?? false)) {
      const asking = path.trim() !== "" && current === null && toCheck(path.trim()) !== null;
      missing.push({ text: asking ? "wait for the check" : "choose a place", focus: toWhere });
    }
  }
  if (providerList === null) missing.push({ text: "wait for the agent CLIs", focus: openTeam(teamRefs.agent) });
  else if (providers === null || (chosenProvider === null && !noLogin)) {
    // none chosen, or the list did not load: its error stands under Agent
    missing.push({ text: "choose an agent", focus: openTeam(teamRefs.agent) });
  }
  if (noLogin?.installed) missing.push({ text: `log in to ${noLogin.title}`, focus: openTeam(teamRefs.agent) });
  if (kits.length === 0) missing.push({ text: "choose a team setup", focus: openTeam(teamRefs.kits) });
  if (model.blocked) {
    missing.push({
      text: "fix the model",
      focus: () => {
        setTeamOpen(true);
        focusNext(model.focus);
      },
    });
  }
  if (promptOver) missing.push({ text: "shorten the task", focus: () => taskRef.current?.focus() });
  const startOff = !ready && busy === null;
  const toStart = startOff && missing.length > 0 ? missing : [];

  // Team's explanation: where its settings come from.
  const teamAbout = resuming
    ? "As when it stopped. A change takes effect from now on."
    : [
        fromLast
          ? "As in the last session in this folder."
          : suggested === "last_any"
            ? "Agent as in your last session; setup and permissions are LADO's defaults."
            : "Setup and permissions are LADO's defaults.",
        named && (named.name_state === "running" || named.name_state === "taken_elsewhere") && named.default_name
          ? `"${named.default_name}" is taken by another session.`
          : "",
      ]
        .filter(Boolean)
        .join(" ");

  // The agent's notes: the list's state, a CLI that cannot run, a login missing.
  const providersNote =
    providerList !== null && "error" in providerList ? (
      <span className="field-note bad">{providerList.error}</span>
    ) : providerList === null ? (
      <span className="field-note">checking the agent CLIs…</span>
    ) : null;
  const agentNote = noLogin?.installed ? (
    // A new session or a resume of it is refused (lado.logins).
    <span className="field-note bad">
      {noLogin.title} is not logged in: its agents cannot start.{" "}
      <button type="button" className="link-button" onClick={() => leave(agentClisPath(noLogin.name))}>
        Log in first
      </button>
    </span>
  ) : providers !== null && providerInfo === null && chosenProvider !== null ? (
    <span className="field-note bad">unknown agent CLI {chosenProvider}</span>
  ) : providerInfo && !providerInfo.installed ? (
    <span className="field-note bad">{`${providerInfo.detail}; ${providerInfo.install_hint}`}</span>
  ) : serverOnly ? (
    // A start on a server's model needs no login of the CLI (runtime.check_login).
    <span className="field-note">
      {serverOnly.title} is not logged in: its agents run on your server's models only.{" "}
      <button type="button" className="link-button" onClick={() => leave(agentClisPath(serverOnly.name))}>
        Log in
      </button>{" "}
      for its own models.
    </span>
  ) : providerInfo?.warning ? (
    <span className="field-note warn">⚠ {providerInfo.warning}</span>
  ) : null;

  const nameNote = taken ? (
    <>
      <span className="field-note bad" role="alert">
        {taken.message}
      </span>
      <button
        type="button"
        className="quiet"
        onClick={() => {
          setName(nextName(shownName));
          setRefused(null);
        }}
      >
        {`Use ${nextName(shownName)}`}
      </button>
    </>
  ) : null;

  const generalRefusal = refused !== null && taken === null && modelRefusal === null;
  const notesId = `${ids}-place-notes`;
  const busyNow = busy !== null || waiting;

  return (
    <dialog
      ref={dialog}
      className="launch-dialog"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        if (busy === null) close();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Escape" || event.defaultPrevented) return;
        event.preventDefault();
        if (busy === null) close();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          start();
        }}
      >
        <div className="launch-head">
          <h2>{title}</h2>
          <button type="button" className="ghost launch-x" aria-label="Close" onClick={close} disabled={busy !== null}>
            ×
          </button>
        </div>

        <div className="launch-body">
          {resuming && (
            <div className="resume-status">
              <p>
                <b>{resuming.name}</b>
                {` · ${resuming.stopped_at ? `stopped ${since(resuming.stopped_at)} ago` : "stopped"} `}
                <InfoTip about="Resume">{RESUME_ABOUT}</InfoTip>
              </p>
              <button
                type="button"
                className="quiet"
                disabled={busyNow}
                onClick={() =>
                  onMode(
                    resuming.project
                      ? { kind: "new", project: resuming.project, repo: lastPart(resuming.repo) }
                      : { kind: "new", path: resuming.repo },
                  )
                }
              >
                Start a new session instead
              </button>
            </div>
          )}

          <div className="field launch-where" role="group" aria-labelledby={`${ids}-where-label`}>
            <span className="field-label" id={`${ids}-where-label`}>
              {resuming ? <span>Where</span> : <label htmlFor={`${ids}-where`}>Where</label>}
              {projecting && projectRepo && chosenProject && !projectPick && (
                <InfoTip about="Where">
                  {`${projectRepo.name} is a repository of the project ${projectTitle}: the team works with ${projectTitle}'s keys and settings.`}
                </InfoTip>
              )}
            </span>
            {resuming ? (
              <div className="where-fixed">
                <PlaceIcon icon={resuming.project ? "project" : "folder"} />
                <span>
                  <span className="place-name">{lastPart(resuming.repo)}</span> <span className="where-path">{resuming.repo}</span>
                </span>
              </div>
            ) : (
              <PlaceBox
                id={`${ids}-where`}
                shown={shown}
                recent={recent}
                inputRef={whereRef}
                describedBy={notesId}
                disabled={busyNow}
                onRecent={(place: RecentFolder) => {
                  setRefused(null);
                  setInclude([]);
                  if (place.project?.repo) {
                    toProject({ id: place.project.id, title: place.project.title, repo: place.project.repo });
                  } else {
                    toFolder(place.path);
                  }
                  focusNext(() => taskRef.current?.focus());
                }}
                onPath={(where) => {
                  setRefused(null);
                  setInclude([]);
                  toFolder(where);
                }}
                onWay={(way) => {
                  setRefused(null);
                  setInclude([]);
                  setSource(way);
                  if (way === "folder") {
                    setOtherFolder(true);
                    setPath("");
                    focusNext(() => pathRef.current?.focus());
                  } else if (way === "project") {
                    setProjectPick(true);
                    setProjectAsk({ project: null, repo: null });
                  } else if (way === "url") focusNext(() => urlRef.current?.focus());
                  else if (way === "scratch") focusNext(() => scratchRef.current?.focus());
                }}
              />
            )}
            {!resuming && source === "folder" && otherFolder && (
              <FolderPathField
                path={path}
                onPath={(next) => {
                  placeTouched.current = true;
                  setPath(next);
                  setRefused(null);
                  setInclude([]);
                }}
                workspace={workspace}
                disabled={busyNow}
                inputRef={pathRef}
                describedBy={notesId}
              />
            )}
            {!resuming && source === "folder" && (
              <FolderNotes
                id={notesId}
                folder={shownFolder}
                checking={toCheck(path.trim()) !== null && shownFolder === null}
                problem={checked !== null && "error" in checked ? checked.error : null}
                stopped={stopped ? { name: stopped.name, at: stopped.stopped_at } : null}
                disabled={busyNow}
                onScratch={toScratch}
                onProject={toProject}
                setup={
                  shownFolder?.setup ? (
                    <LaunchSetup
                      id={`${ids}-setup`}
                      setup={shownFolder.setup}
                      include={include}
                      onInclude={setInclude}
                      checkingAgain={rechecking}
                      onCheckAgain={() => setCheckTurn((turn) => turn + 1)}
                    />
                  ) : null
                }
              />
            )}
            {projecting && !projectPick && projectRepo && (
              <div id={notesId} className="place-notes">
                <p className="place-line">
                  <span className="ok">{`✓ Ready${projectRepo.branch ? ` · branch ${projectRepo.branch}` : ""}`}</span>
                  {stopped && (
                    <>
                      {" · Session "}
                      <b>{stopped.name}</b>
                      {` stopped here${stopped.stopped_at ? ` ${since(stopped.stopped_at)} ago` : ""}`}
                    </>
                  )}
                </p>
              </div>
            )}
            {projecting && (projectPick || (inProject !== null && projectRepo === null)) && (
              <ProjectField
                launch={shownProject}
                asked={projectAsk}
                asking={inProject === null}
                problem={projectAsked !== null && "error" in projectAsked ? projectAsked.error : null}
                disabled={busyNow}
                onProject={(project) => {
                  setProjectAsk({ project, repo: null });
                  setRefused(null);
                }}
                onRepo={(repo) => {
                  setProjectAsk({ project: shownProject?.project ?? null, repo });
                  setRefused(null);
                }}
                onLeave={leave}
              />
            )}
            {projecting && !projectPick && projectRepo === null && projectAsked !== null && "error" in projectAsked && (
              <span className="field-note bad">{projectAsked.error}</span>
            )}
            {scratching && (
              <ScratchNameField
                text={scratchText}
                onText={(next) => {
                  setScratchText(next);
                  setRefused(null);
                }}
                target={fresh}
                problem={scratchAsked !== null && "error" in scratchAsked ? scratchAsked.error : null}
                workspace={workspace}
                disabled={busyNow}
                inputRef={scratchRef}
                onProject={toProject}
              />
            )}
            {cloning && (
              <>
                <UrlField
                  url={url}
                  onUrl={(next) => {
                    placeTouched.current = true;
                    setUrl(next);
                    setRefused(null);
                    setCloneEnd(null);
                  }}
                  listing={typedUrl !== "" && remote === null && (remoteAsked === null || branchesUrl !== typedUrl)}
                  remote={remote}
                  failed={branchesUrl === typedUrl && remoteAsked !== null && "error" in remoteAsked ? remoteAsked : null}
                  disabled={busyNow}
                  inputRef={urlRef}
                />
                <div className="launch-grid">
                  <BranchField
                    remote={remote}
                    failed={branchesUrl === typedUrl && remoteAsked !== null && "error" in remoteAsked}
                    branch={branch}
                    onBranch={(next) => setPicked({ url: typedUrl, branch: next })}
                    disabled={busyNow}
                  />
                  <div className="field launch-where">
                    <label htmlFor={`${ids}-into`}>Clone into</label>
                    <input
                      id={`${ids}-into`}
                      value={into ?? target?.path ?? ""}
                      placeholder={inWorkspace("<repo>")}
                      autoComplete="off"
                      spellCheck={false}
                      disabled={busyNow}
                      onChange={(event) => setInto(event.target.value)}
                    />
                    <TargetNote
                      target={target}
                      problem={targetAsked !== null && "error" in targetAsked ? targetAsked.error : null}
                      onProject={toProject}
                    />
                    {target?.warning && <span className="field-note warn">⚠ {target.warning}</span>}
                  </div>
                </div>
                {target && (target.state === "same_repo" || target.state === "other_repo") && (
                  <div className={`field-note ${target.state === "same_repo" ? "ok" : "bad"}`}>
                    {target.state === "same_repo"
                      ? `✓ ${target.text}. LADO will use it as it is: no clone, no pull, no branch switch.`
                      : target.text}
                  </div>
                )}
                {job && <CloneProgress job={job} />}
              </>
            )}
            {cloneEnd && "note" in cloneEnd && (
              <p className="field-note" role="status">
                {cloneEnd.note}
              </p>
            )}
            {cloneEnd && "refused" in cloneEnd && (
              <div className="launch-refused">
                <p className="problem" role="alert">
                  {cloneEnd.refused.message}
                </p>
                {cloneEnd.refused.hint && (
                  <FolderHint text={cloneEnd.refused.hint.text} command={cloneEnd.refused.hint.command} />
                )}
              </div>
            )}
          </div>

          <div className="field launch-task">
            <span className="field-label">
              <label htmlFor={`${ids}-task`}>{resuming ? "Message" : "Task"}</label>{" "}
              <InfoTip about={resuming ? "Message" : "Task"}>{resuming ? MESSAGE_ABOUT : TASK_ABOUT}</InfoTip>
            </span>
            <textarea
              ref={taskRef}
              id={`${ids}-task`}
              rows={3}
              value={prompt}
              disabled={busyNow}
              placeholder={resuming ? "What should the team do next?" : "What should the team do?"}
              aria-invalid={promptOver || undefined}
              aria-describedby={promptOver ? `${ids}-task-note` : undefined}
              onChange={(event) => setPrompt(event.target.value)}
            />
            {promptOver && (
              <span id={`${ids}-task-note`} className="field-note bad">
                {promptText.length} characters, the limit is {maxMessage}
              </span>
            )}
          </div>

          <LaunchTeam
            open={teamOpen}
            onOpen={setTeamOpen}
            about={teamAbout}
            modelPeek={model.peek}
            name={resuming ? null : shownName}
            onName={setName}
            nameFixed={scratching}
            nameNote={nameNote}
            kits={kits}
            onKits={(next) => {
              touch("kits");
              setKits(next);
            }}
            known={valueOf(kitList) ?? []}
            kitsError={kitList !== null && "error" in kitList ? kitList.error : null}
            providers={providers}
            providersNote={providersNote}
            chosen={chosenProvider}
            info={providerInfo}
            onProvider={chooseProvider}
            agentNote={agentNote}
            mode={modeWords(providerInfo).length ? permissionMode : DEFAULT_MODE}
            onMode={(next) => {
              touch("mode");
              setModeNote(null);
              setPermissionMode(next);
            }}
            modeNote={modeNote}
            modelField={model.field}
            without={without}
            onWithout={(next) => {
              touch("without");
              setWithout(next);
            }}
            switchOff={switchOff}
            disabled={busyNow}
            refs={teamRefs}
          />

          {generalRefusal && (
            <div className="launch-refused" ref={refusedRef} tabIndex={-1}>
              <p className="problem" role="alert">
                {refused.message}
              </p>
            </div>
          )}
          {modelRefusal && (
            <p className="problem" role="alert">{`Not started: ${modelRefusal.short}. See Model above.`}</p>
          )}
          {resuming && <ActionProblem attempt={attempt} />}
        </div>

        <div className="launch-buttons">
          {toStart.length > 0 && (
            <p className="launch-missing" id={`${ids}-missing`}>
              {"To start: "}
              {toStart.map((one, i) => (
                <span key={one.text}>
                  {i > 0 && (i === toStart.length - 1 ? " and " : ", ")}
                  <button type="button" className="link-button" onClick={one.focus}>
                    {one.text}
                  </button>
                </span>
              ))}
              .
            </p>
          )}
          {job ? (
            <button type="button" className="launch-cancel" onClick={clone.cancel}>
              Cancel clone
            </button>
          ) : (
            <button type="button" className="launch-cancel" onClick={close} disabled={busy !== null}>
              Cancel
            </button>
          )}
          <MaybeWaits resuming={resuming !== null}>
            <button
              ref={actionRef}
              type="submit"
              className="primary"
              disabled={startOff || undefined}
              aria-disabled={busyNow || undefined}
              aria-describedby={toStart.length ? `${ids}-missing` : undefined}
              onClick={(event) => {
                event.preventDefault();
                start();
              }}
            >
              {busy !== null ? busyLabel[busy] : startLabel}
            </button>
          </MaybeWaits>
        </div>
      </form>
    </dialog>
  );
}

const hasSwitchOff = (detail: unknown) =>
  detail !== null && typeof detail === "object" && "switch_off" in detail && Array.isArray((detail as Refused).switch_off);

// A 409 refused for the model: the field's, not a session that has the name.
const isModelRefusal = (detail: unknown): detail is ModelRefusal =>
  typeof detail === "object" && detail !== null && "field" in detail && detail.field === "model";

// Resume's button waits for the connection; New session's does not.
const MaybeWaits = ({ resuming, children }: { resuming: boolean; children: React.ReactElement<object> }) =>
  resuming ? <Waits>{children}</Waits> : children;

export function CloneProgress({ job }: { job: CloneJob }) {
  const progress = job.progress;
  const percent = progress?.percent ?? 0;
  return (
    <div className="clone-progress" role="status">
      <div className="clone-line">
        <span>
          <b>{progress?.phase ?? "Starting git"}</b> · {percent}%
        </span>
        <span>{progress?.detail ?? ""}</span>
      </div>
      <div
        className="clone-bar"
        role="progressbar"
        aria-label="Clone"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="clone-line">
        <span>
          cloning {job.branch ? `branch ${job.branch}` : "the default branch"} into {job.path} · {elapsed(job.seconds)}
        </span>
      </div>
    </div>
  );
}
