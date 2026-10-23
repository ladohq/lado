// The New session window (docs/design/ui.md, Launch and session control): opened from the
// rail's Launch, the session list's "+", and in its Resume mode from a stopped session's
// Resume. What a folder is, which kits and providers there are and whether a name is taken
// all come from the server; the window decides nothing the core decides.
import { createContext, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
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
  type KitInfo,
  type Launch,
  type Limits,
  type ProjectLaunch,
  type ProjectPlace,
  type ProviderInfo,
  type ProviderSuggestion,
  type RecentFolder,
  type RemoteInfo,
  type ScratchTarget,
  type SessionInfo,
  type Refused,
  type Started,
  type Taken,
  type Workspace,
} from "./api";
import { useCloneJob } from "./cloneJob";
import { useCopy } from "./Copy";
import { ProjectField } from "./LaunchProject";
import { useLive } from "./live";
import { projectPath, sessionPath } from "./paths";

// How long the window waits after a keystroke before it asks the server about the folder.
export const DEBOUNCE = 200;
// The same before it asks a remote for its branches, which goes to the network.
export const BRANCHES_DEBOUNCE = 500;
// Up to this many branches the Branch field is a list; more, a field that filters them.
export const BRANCH_LIST = 30;
// The target states a clone may start in (lado.clone.CAN_CLONE).
const CAN_CLONE = new Set<CloneTarget["state"]>(["new", "empty"]);
// The folder states a fresh start may go on in (lado.scratch.CAN_START).
const CAN_START = new Set<ScratchTarget["state"]>(["new", "empty"]);

// Where a new session's folder comes from: made from scratch, one there is, a clone, or a
// project's repository.
type Source = "scratch" | "folder" | "url" | "project";

const DEFAULT_KIT = "default";
const DEFAULT_MODE = "default"; // also "no mode given": the provider's own default
// Why the folder's provider was chosen, in the words `lado start` prints (runtime.Suggestion).
const SUGGESTED: Record<ProviderSuggestion["reason"], string> = {
  last_session: "from the folder's last session",
  only_installed: "the only one installed",
};

// A session of these statuses can be resumed; a running one only opened.
const RESUMABLE = new Set<SessionInfo["status"]>(["stopped", "tmux_gone"]);

// A new session's window opens in Project with `project` chosen (the project's page), else
// in Folder (From scratch without recent folders).
// A new session, in Project with `project` (and its repository `repo`) chosen when given.
export type LaunchMode = { kind: "new"; project?: string; repo?: string } | { kind: "resume"; session: SessionInfo };

const LaunchContext = createContext<(mode?: LaunchMode) => void>(() => {});

// Opens the New session window, or its Resume mode for a session.
export const useLaunch = () => useContext(LaunchContext);

// What a start or resume said, for the session's page to show (its problems until closed).
export type StartedState = { started: Started };

export function LaunchProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<LaunchMode | null>(null);
  return (
    <LaunchContext.Provider value={(next = { kind: "new" }) => setMode(next)}>
      {children}
      {mode && (
        <LaunchDialog
          key={mode.kind === "resume" ? `resume:${mode.session.name}` : "new"}
          mode={mode}
          onMode={setMode}
          onClose={() => setMode(null)}
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
type Asked<T> = { value: T } | { error: string; detail?: unknown } | null;

// The server's answer to `ask(key)`, asked again when `key` changes; nothing for a null key.
function useAsked<T>(key: string | null, ask: (key: string) => Promise<T>): Asked<T> {
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

const valueOf = <T,>(asked: Asked<T>): T | null => (asked !== null && "value" in asked ? asked.value : null);

// Where suggestions come from (N1): the folder up to the last "/" and the name typed after it.
function parentOf(path: string): { parent: string; prefix: string } | null {
  const slash = path.lastIndexOf("/");
  if (slash < 0) return null;
  return { parent: path.slice(0, slash + 1), prefix: path.slice(slash + 1) };
}

// The workspace as a parent: "/" stays "/", "/a/b" becomes "/a/b/".
const withSlash = (folder: string) => (folder.endsWith("/") ? folder : `${folder}/`);

const sameFolder = (path: string, folder: string | null) => folder !== null && withSlash(path) === withSlash(folder);

const splitWithout = (text: string) => text.split(/[\s,]+/).filter(Boolean);

// "agent:reviewer@kit-a" as the button that switches it off says it.
const switchOffLabel = (item: string) => {
  const [, rest = item] = item.split(/:(.*)/);
  const [name, kit] = rest.split("@");
  return kit ? `Switch off ${name} of ${kit}` : `Switch off ${name}`;
};

const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((one, i) => one === b[i]);

// A refusal's detail as a CloneRefused, when it is one (its hint shown with Copy).
const cloneRefused = (detail: unknown): CloneRefused | null =>
  detail !== null && typeof detail === "object" && "kind" in detail ? (detail as CloneRefused) : null;

const elapsed = (seconds: number) => {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
};

// The branch a clone takes unless the human picks one: the remote's default, else main,
// else master, else the first.
const defaultBranch = (remote: RemoteInfo) =>
  remote.default ?? ["main", "master"].find((one) => remote.branches.includes(one)) ?? remote.branches[0];

function LaunchDialog({
  mode,
  onMode,
  onClose,
}: {
  mode: LaunchMode;
  onMode: (mode: LaunchMode) => void;
  onClose: () => void;
}) {
  const resuming = mode.kind === "resume" ? mode.session : null;
  const dialog = useRef<HTMLDialogElement>(null);
  const advanced = useRef<HTMLDetailsElement>(null);
  const navigate = useNavigate();
  const live = useLive();
  const ids = useId();

  const [path, setPath] = useState(resuming?.repo ?? "");
  const [name, setName] = useState<string | null>(resuming?.name ?? null); // null: the default
  const [kits, setKits] = useState<string[]>(resuming?.kits ?? [DEFAULT_KIT]);
  // null: none chosen; a new session's comes from the folder's suggestion (the core's rule)
  const [provider, setProvider] = useState<string | null>(resuming?.provider ?? null);
  const [suggested, setSuggested] = useState<ProviderSuggestion["reason"] | null>(null);
  const [permissionMode, setPermissionMode] = useState(resuming?.permission_mode ?? DEFAULT_MODE);
  const [without, setWithout] = useState(resuming?.without.join(", ") ?? "");
  const [prompt, setPrompt] = useState(""); // the human's first message to the supervisor
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [fromLast, setFromLast] = useState(false);
  const [modeNote, setModeNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<ApiError | null>(null);
  // Clone from URL: the URL, the folder (null: the default one), the branch the human picked
  // for which URL, the running job, and what the last clone ended in.
  // The source starts in Folder and becomes From scratch once the recent folders are none,
  // unless the human picked one or typed a folder or URL before (sourceTouched).
  const asksProject = mode.kind === "new" ? (mode.project ?? null) : null;
  const [source, setSourceState] = useState<Source>(asksProject ? "project" : "folder");
  const sourceTouched = useRef(asksProject !== null);
  // Project: the project and repository asked of the server (null: its choice).
  const [projectAsk, setProjectAsk] = useState<{ project: string | null; repo: string | null }>({
    project: asksProject,
    repo: (asksProject && mode.kind === "new" && mode.repo) || null,
  });
  const setSource = (next: Source) => {
    sourceTouched.current = true;
    setSourceState(next);
  };
  // From scratch: the name as typed and the folder (null: the name's default one).
  const [scratchText, setScratchText] = useState("");
  const [scratchInto, setScratchInto] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [into, setInto] = useState<string | null>(null);
  const [picked, setPicked] = useState<{ url: string; branch: string } | null>(null);
  const clone = useCloneJob(); // its beacon cancels the clone of a page that goes away
  const job = clone.job;
  const [cloneEnd, setCloneEnd] = useState<{ note: string } | { refused: CloneRefused } | null>(null);
  const branchesAsked = useRef(new Map<string, Promise<RemoteInfo>>());

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

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
  // Start names the project the session goes to: the window opens on the last one used,
  // and another project's session gets another client's keys.
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
      const [text, path] = JSON.parse(key) as [string, string];
      return getScratchTarget(text, path || null);
    },
  );
  const fresh =
    settledText === typedText && settledScratchInto === typedScratchInto ? valueOf(scratchAsked) : null;
  const typedUrl = url.trim();
  const typedInto = (into ?? "").trim();
  const settledUrl = useDebounced(typedUrl);
  const settledInto = useDebounced(typedInto);
  const targetAsked = useAsked(cloning && settledUrl ? JSON.stringify([settledUrl, settledInto]) : null, (key) => {
    const [asked, path] = JSON.parse(key) as [string, string];
    return getCloneTarget(asked, path || null);
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
  const checked = useAsked(resuming ? null : toCheck(settled), getFolder);
  const folder = valueOf(checked);
  const current = folder !== null && folder.path === settled && settled === path.trim() ? folder : null;
  const recentAsked = valueOf(useOnce(getRecentFolders, resuming !== null));
  const recent = recentAsked ?? [];
  useEffect(() => {
    if (recentAsked === null || sourceTouched.current) return;
    sourceTouched.current = true; // decided once
    if (recentAsked.length === 0) setSourceState("scratch");
  }, [recentAsked]);
  // In Project the repository's git root (links resolved), as a session's folder is given.
  const root = resuming?.repo ?? (scratching ? null : projecting ? inProject?.root : folder?.root) ?? null;
  const kitList = useAsked(root ?? "", (where) => getKits(where || null));
  const providerList = useOnce(getProviders);
  const providers = valueOf(providerList);
  // Without the limits the server checks the first message's length alone.
  const maxMessage = valueOf(useOnce<Limits>(getLimits))?.max_message ?? null;
  const promptText = prompt.trim();
  const promptOver = maxMessage !== null && promptText.length > maxMessage;
  const withPrompt = promptText ? { prompt: promptText } : {};

  const chosenProvider = provider;
  const providerInfo = providers?.find((one) => one.name === chosenProvider) ?? null;
  const modes = providerInfo?.permission_modes ?? [];

  // M5: kits, provider and mode of a new session come from the folder's last session; in
  // Project, from the repository's last session in the project.
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

  // No provider is the default: the folder's suggestion (a clone's or a fresh start's
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

  const named = cloning ? target : projecting ? shownProject : current;
  const shownName = name ?? named?.default_name ?? "";
  const resumable = (sessionName: string) => {
    const loaded = live.sessions;
    return loaded && "sessions" in loaded ? loaded.sessions.find((one) => one.name === sessionName) : undefined;
  };
  const resumeIt = (sessionName: string) => {
    const found = resumable(sessionName);
    if (found) onMode({ kind: "resume", session: found });
  };

  const chooseProvider = (next: string) => {
    touch("provider");
    setProvider(next);
    setSuggested(null);
    const info = providers?.find((one) => one.name === next);
    const supported = info?.permission_modes ?? [];
    if (permissionMode !== DEFAULT_MODE && !supported.includes(permissionMode)) {
      setModeNote(`${next} has no mode ${permissionMode}: set to default`);
      setPermissionMode(DEFAULT_MODE);
    } else {
      setModeNote(null);
    }
  };

  // The provider's part holds in both modes: it is the condition under which ProviderNote
  // shows no refusal. Resume does not check its folder.
  const ready =
    (resuming !== null || (current?.ok ?? false)) &&
    providerInfo?.installed === true &&
    kits.length > 0 &&
    !promptOver;
  const cloneReady =
    !promptOver &&
    remote !== null &&
    target !== null &&
    CAN_CLONE.has(target.state) &&
    providerInfo?.installed === true &&
    kits.length > 0 &&
    shownName !== "";
  const scratchReady =
    !promptOver &&
    fresh !== null &&
    fresh.path !== null &&
    fresh.name !== null &&
    CAN_START.has(fresh.state) &&
    fresh.author === null &&
    fresh.name_state === "free" &&
    providerInfo?.installed === true &&
    kits.length > 0;
  const projectReady =
    !promptOver && projectRepo !== null && providerInfo?.installed === true && kits.length > 0 && shownName !== "";

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
      ...withPrompt,
    });
  };

  const opened = (started: Started) => {
    onClose();
    const state: StartedState = { started };
    navigate(sessionPath(started.session.name, "activity"), { state });
  };

  const toFolder = (where: string) => {
    setSource("folder");
    setPath(where);
  };

  // Start from scratch here: the folder checked in Folder, in Create in, its name in Name.
  const toScratch = (where: string) => {
    setSource("scratch");
    setScratchInto(where);
    setScratchText(where.replace(/\/+$/, "").split("/").pop() ?? "");
    setRefused(null);
  };

  // Folder's refusal inside a project: Project with its repository, or the project's page.
  const toProject = (place: ProjectPlace) => {
    if (place.repo === null) {
      leave(projectPath(place.id));
      return;
    }
    setSource("project");
    setProjectAsk({ project: place.id, repo: place.repo });
    setRefused(null);
  };

  const leave = (to: string) => {
    onClose();
    navigate(to);
  };

  // Make the folder a repository and start there; a start refused after the repository
  // was made leaves the window in Folder with it and the refusal, as after a clone.
  const createAndStart = async () => {
    if (fresh?.path == null) return;
    const where = fresh.path;
    setBusy(true);
    setRefused(null);
    try {
      opened(await startIn({ kind: "scratch", path: where }));
    } catch (error) {
      const given = error instanceof ApiError ? error : new ApiError(0, String(error));
      if (given.status === 400 || given.status === 409) {
        const made = await getFolder(where).catch(() => null);
        if (made?.ok) toFolder(where);
      }
      setRefused(given);
      setBusy(false);
    }
  };

  // Clone, then start in the clone as Start does for a folder; a start refused after the
  // clone leaves the window in Folder with the clone and the refusal.
  const cloneAndStart = async () => {
    if (target === null || branch === null) return;
    setBusy(true);
    setRefused(null);
    setCloneEnd(null);
    const refuse = (error: unknown) => {
      const given = error instanceof ApiError ? error : new ApiError(0, String(error));
      const why = cloneRefused(given.detail);
      setCloneEnd({ refused: why ?? { message: given.message, kind: "refused", hint: null } });
      setBusy(false);
    };
    const asked = typedUrl; // its field is off while the clone runs
    // A job the server dropped (clone.KEPT) ended while this window did not ask: the clone
    // is there when the folder is now a clone of the URL.
    const isThere = async (lost: CloneJob) =>
      (await getCloneTarget(asked, lost.path)).state === "same_repo";
    let end;
    try {
      end = await clone.run({ url: asked, path: target.path, branch }, isThere);
    } catch (error) {
      refuse(error);
      return;
    }
    if ("ended" in end) {
      if (end.ended === "left") return;
      if (end.ended === "gone") {
        refuse(end.error); // the job's end is unknown
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
      opened(await startIn({ kind: "folder", path: running.path }));
    } catch (error) {
      toFolder(running.path);
      setRefused(error instanceof ApiError ? error : new ApiError(0, String(error)));
      setBusy(false);
    }
  };

  const submit = async () => {
    setBusy(true);
    setRefused(null);
    const off = splitWithout(without);
    try {
      let started: Started;
      if (resuming) {
        const changed: Record<string, unknown> = {};
        if (!sameList(kits, resuming.kits)) changed.kits = kits;
        if (chosenProvider !== null && chosenProvider !== resuming.provider) changed.provider = chosenProvider;
        if (permissionMode !== (resuming.permission_mode ?? DEFAULT_MODE)) changed.permission_mode = permissionMode;
        if (!sameList(off, resuming.without)) changed.without = off;
        started = await resumeSession(resuming.name, { ...changed, ...withPrompt });
      } else {
        started = await startIn(
          projecting && inProject?.project && projectRepo
            ? { kind: "project", project: inProject.project, repo: projectRepo.name }
            : { kind: "folder", path: path.trim() },
        );
      }
      opened(started);
    } catch (error) {
      setRefused(error instanceof ApiError ? error : new ApiError(0, String(error)));
      setBusy(false);
    }
  };

  const title = resuming ? "Resume session" : "New session";
  const taken = refused?.status === 409 ? (refused.detail as Taken) : null;
  // The session that has the name is this folder's (in Project: of this project too, as
  // the core resumes none of another project or none): Resume it or Open it.
  const takenHere =
    taken !== null &&
    taken.repo === root &&
    (!projecting || (resumable(shownName)?.project ?? null) === (inProject?.project ?? null));
  const detail = refused?.status === 400 ? refused.detail : null;
  const switchOff =
    detail !== null && typeof detail === "object" && "switch_off" in detail ? (detail as Refused).switch_off : [];
  const addSwitchOff = (item: string) => {
    const listed = splitWithout(without);
    if (!listed.includes(item)) setWithout([...listed, item].join(", "));
    if (advanced.current) advanced.current.open = true;
  };

  return (
    <dialog
      ref={dialog}
      className="launch-dialog"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Escape" || event.defaultPrevented) return;
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (busy) return;
          if (source === "folder" && ready) void submit();
          if (projecting && projectReady) void submit();
          if (cloning && cloneReady) void cloneAndStart();
          if (scratching && scratchReady) void createAndStart();
        }}
      >
        <div className="launch-head">
          <h2>{title}</h2>
          <button type="button" className="ghost" aria-label="Close" onClick={onClose} disabled={busy}>
            ×
          </button>
        </div>

        {scratching ? (
          <ScratchNameField
            text={scratchText}
            onText={(next) => {
              setScratchText(next);
              setRefused(null);
            }}
            target={fresh}
            problem={scratchAsked !== null && "error" in scratchAsked ? scratchAsked.error : null}
            head={<SourceSwitch source={source} onSource={setSource} disabled={busy} />}
            disabled={busy}
          />
        ) : projecting ? (
          <ProjectField
            launch={shownProject}
            asking={inProject === null}
            problem={projectAsked !== null && "error" in projectAsked ? projectAsked.error : null}
            head={<SourceSwitch source={source} onSource={setSource} disabled={busy} />}
            disabled={busy}
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
        ) : cloning ? (
          <UrlField
            url={url}
            onUrl={(next) => {
              sourceTouched.current = true;
              setUrl(next);
              setRefused(null);
              setCloneEnd(null);
            }}
            listing={typedUrl !== "" && remote === null && (remoteAsked === null || branchesUrl !== typedUrl)}
            remote={remote}
            failed={branchesUrl === typedUrl && remoteAsked !== null && "error" in remoteAsked ? remoteAsked : null}
            head={<SourceSwitch source={source} onSource={setSource} disabled={busy} />}
            disabled={busy}
          />
        ) : (
          <WhereField
            path={path}
            onPath={(next) => {
              sourceTouched.current = true;
              setPath(next);
              setRefused(null);
            }}
            onScratch={toScratch}
            onProject={toProject}
            folder={current}
            checking={!resuming && toCheck(path.trim()) !== null && current === null}
            problem={checked !== null && "error" in checked ? checked.error : null}
            recent={recent}
            workspace={workspace}
            disabled={busy || resuming !== null}
            head={resuming ? null : <SourceSwitch source={source} onSource={setSource} disabled={busy} />}
          />
        )}

        <div className="launch-grid">
          {scratching && (
            <div className="field launch-where launch-wide">
              <label htmlFor={`${ids}-create-in`}>Create in</label>
              <input
                id={`${ids}-create-in`}
                value={scratchInto ?? fresh?.path ?? ""}
                placeholder={inWorkspace("<name>")}
                autoComplete="off"
                spellCheck={false}
                disabled={busy}
                onChange={(event) => {
                  setScratchInto(event.target.value);
                  setRefused(null);
                }}
              />
              {fresh?.text &&
                (CAN_START.has(fresh.state) ? (
                  <span className="field-note ok">✓ {fresh.text}</span>
                ) : (
                  <RefusedNote text={fresh.text} hint={fresh.hint ?? null} />
                ))}
              {fresh?.warning && <span className="field-note warn">⚠ {fresh.warning}</span>}
            </div>
          )}
          {cloning && (
            <>
              <div className="field launch-where">
                <label htmlFor={`${ids}-into`}>Clone into</label>
                <input
                  id={`${ids}-into`}
                  value={into ?? target?.path ?? ""}
                  placeholder={inWorkspace("<repo>")}
                  autoComplete="off"
                  spellCheck={false}
                  disabled={busy}
                  onChange={(event) => setInto(event.target.value)}
                />
                <TargetNote
                  target={target}
                  problem={targetAsked !== null && "error" in targetAsked ? targetAsked.error : null}
                />
                {target?.warning && <span className="field-note warn">⚠ {target.warning}</span>}
              </div>
              <BranchField
                remote={remote}
                failed={branchesUrl === typedUrl && remoteAsked !== null && "error" in remoteAsked}
                branch={branch}
                onBranch={(next) => setPicked({ url: typedUrl, branch: next })}
                disabled={busy}
              />
            </>
          )}
          {!scratching && (
            <div className="field">
              <label htmlFor={`${ids}-name`}>Name</label>
              <input
                id={`${ids}-name`}
                value={shownName}
                disabled={busy || resuming !== null}
                onChange={(event) => setName(event.target.value)}
              />
              {!resuming && name === null && named && (
                <NameHint folder={named} disabled={busy} onResume={() => resumeIt(named.default_name ?? "")} />
              )}
            </div>
          )}

          <KitsField
            root={root}
            listed={kitList}
            kits={kits}
            disabled={busy}
            fromLast={fromLast}
            onKits={(next) => {
              touch("kits");
              setKits(next);
            }}
          />

          <div className="field">
            <label htmlFor={`${ids}-provider`}>Provider</label>
            <select
              id={`${ids}-provider`}
              value={providers ? (chosenProvider ?? "") : ""}
              disabled={busy || providers === null}
              onChange={(event) => chooseProvider(event.target.value)}
            >
              {providers === null ? (
                <option value="">checking…</option>
              ) : (
                <>
                  {chosenProvider === null && (
                    <option value="" disabled>
                      choose…
                    </option>
                  )}
                  {/* A chosen name the list lacks (a resumed session's) gets its own option,
                      or the select would show the first one, and picking it would be no change. */}
                  {chosenProvider !== null && providerInfo === null && (
                    <option value={chosenProvider} disabled>
                      {`${chosenProvider} · unknown`}
                    </option>
                  )}
                  {providers.map((one) => (
                    <option key={one.name} value={one.name} disabled={!one.installed}>
                      {one.installed ? `${one.name} · ${one.title} ${one.version}`.trim() : `${one.name} · not installed`}
                    </option>
                  ))}
                </>
              )}
            </select>
            <ProviderNote asked={providerList} info={providerInfo} chosen={chosenProvider} />
            {providers !== null && chosenProvider === null && (
              <span className="field-note">choose the agent CLI for this session</span>
            )}
            {suggested !== null && providerInfo?.installed && (
              <span className="field-note">{SUGGESTED[suggested]}</span>
            )}
          </div>

          <div className="field">
            <label htmlFor={`${ids}-mode`}>Permission mode</label>
            <select
              id={`${ids}-mode`}
              value={modes.length ? permissionMode : DEFAULT_MODE}
              disabled={busy || modes.length === 0}
              onChange={(event) => {
                touch("mode");
                setModeNote(null);
                setPermissionMode(event.target.value);
              }}
            >
              {(modes.length ? modes : [DEFAULT_MODE]).map((one) => (
                <option key={one} value={one}>
                  {one}
                </option>
              ))}
            </select>
            <span className="field-note">
              {modeNote ??
                (providerInfo === null
                  ? ""
                  : modes.length
                    ? `the modes ${providerInfo.name} supports`
                    : `${providerInfo.name} takes no permission mode`)}
            </span>
          </div>
        </div>

        <FirstMessage text={prompt} onText={setPrompt} limit={maxMessage} disabled={busy} />

        <details className="launch-advanced" ref={advanced}>
          <summary>Advanced: switch off agents, skills, MCP servers or flows</summary>
          <label className="field">
            Switch off
            <input
              value={without}
              disabled={busy}
              placeholder="agent:reviewer@kit-b, skill:style"
              onChange={(event) => setWithout(event.target.value)}
            />
          </label>
          <span className="field-note">
            kind:name or kind:name@kit, separated by commas; kinds: agent, skill, mcp, flow
          </span>
        </details>

        {cloning && target && (target.state === "same_repo" || target.state === "other_repo") && (
          <div className={`field-note ${target.state === "same_repo" ? "ok" : "bad"}`}>
            {target.state === "same_repo"
              ? `✓ ${target.text}. LADO will use it as it is: no clone, no pull, no branch switch.`
              : target.text}
          </div>
        )}

        {job && <CloneProgress job={job} />}

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

        {refused && (
          <div className="launch-refused">
            <p className="problem" role="alert">
              {refused.message}
            </p>
            {switchOff.map((item) => (
              <button
                key={item}
                type="button"
                className="quiet"
                disabled={busy || splitWithout(without).includes(item)}
                onClick={() => addSwitchOff(item)}
              >
                {switchOffLabel(item)}
              </button>
            ))}
            {taken && takenHere && RESUMABLE.has(taken.status) && resumable(shownName) && (
              <button type="button" className="quiet" onClick={() => resumeIt(shownName)}>
                Resume it
              </button>
            )}
            {taken && takenHere && !RESUMABLE.has(taken.status) && (
              <button
                type="button"
                className="quiet"
                onClick={() => {
                  onClose();
                  navigate(sessionPath(shownName, "activity"));
                }}
              >
                Open it
              </button>
            )}
          </div>
        )}

        <div className="launch-buttons">
          {job ? (
            <button type="button" className="quiet" onClick={clone.cancel}>
              Cancel clone
            </button>
          ) : (
            <button type="button" className="quiet" onClick={onClose} disabled={busy}>
              Cancel
            </button>
          )}
          {scratching ? (
            <button type="submit" className="primary" disabled={busy || !scratchReady}>
              {busy ? "Starting…" : "Create and start"}
            </button>
          ) : !cloning ? (
            <button type="submit" className="primary" disabled={busy || !(projecting ? projectReady : ready)}>
              {busy
                ? resuming
                  ? "Resuming…"
                  : "Starting…"
                : projectTitle !== null
                  ? `Start in ${projectTitle}`
                  : title === "New session"
                    ? "Start session"
                    : title}
            </button>
          ) : target?.state === "same_repo" && !busy ? (
            <button
              type="button"
              className="primary"
              onClick={() => {
                setRefused(null);
                toFolder(target.path);
              }}
            >
              Use this clone
            </button>
          ) : (
            <button type="submit" className="primary" disabled={busy || !cloneReady}>
              {job ? "Cloning…" : busy ? "Starting…" : "Clone and start"}
            </button>
          )}
        </div>
      </form>
    </dialog>
  );
}

// The human's first message to the supervisor: a row folded each time the window opens,
// which shows the text's first line while folded with text in it.
function FirstMessage({
  text,
  onText,
  limit,
  disabled,
}: {
  text: string;
  onText: (text: string) => void;
  limit: number | null;
  disabled: boolean;
}) {
  const trimmed = text.trim();
  const first = trimmed.split("\n")[0].trim();
  return (
    <details className="launch-advanced launch-first">
      <summary>
        {first ? (
          <>
            First message to the supervisor: <span className="launch-first-peek">{first}</span>
          </>
        ) : (
          "First message to the supervisor (optional)"
        )}
      </summary>
      <div className="field">
        <textarea
          aria-label="First message"
          rows={4}
          value={text}
          disabled={disabled}
          placeholder="What the supervisor should do first"
          onChange={(event) => onText(event.target.value)}
        />
        {limit !== null && trimmed.length > limit ? (
          <span className="field-note bad">
            {trimmed.length} characters, the limit is {limit}
          </span>
        ) : (
          <span className="field-note">
            sent to the supervisor as your message once it starts; its answer comes in the chat
          </span>
        )}
      </div>
    </details>
  );
}

function WhereField({
  path,
  onPath,
  onScratch,
  onProject,
  folder,
  checking,
  problem,
  recent,
  workspace,
  disabled,
  head,
}: {
  path: string;
  onPath: (path: string) => void;
  onScratch: (path: string) => void; // Start from scratch here
  onProject: (place: ProjectPlace) => void; // the refused folder's project
  folder: FolderInfo | null;
  checking: boolean;
  problem: string | null;
  recent: RecentFolder[];
  workspace: Workspace | null; // LADO_REPOS, else ~/workspace; null until it is known
  disabled: boolean;
  head: ReactNode; // the switch to Clone from URL, beside the label
}) {
  const ids = useId();
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const empty = path.trim() === "";
  // An empty field suggests the workspace's subfolders, once it exists.
  const made = workspace?.made ? workspace.path : null;
  const split = empty && made ? { parent: withSlash(made), prefix: "" } : parentOf(path);
  const parent = useDebounced(split?.parent ?? null);
  const listed = valueOf(useAsked(open && parent ? parent : null, getFolder));
  const prefix = (split?.prefix ?? "").toLowerCase();
  const options =
    open && listed && split && listed.path === split.parent
      ? listed.subfolders.filter((one) => one.toLowerCase().startsWith(prefix) && one !== split.prefix)
      : []; // a folder typed in full is not suggested again: its check shows under the field

  const pick = (folderName: string) => {
    if (!split) return;
    onPath(split.parent + folderName);
    setOpen(false);
    setActive(-1);
  };

  return (
    <div className="field launch-where">
      <div className="where-head">
        <label htmlFor={`${ids}-where`}>Where</label>
        {head}
      </div>
      <div className="where-box">
        <input
          ref={input}
          id={`${ids}-where`}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={options.length > 0}
          aria-controls={`${ids}-folders`}
          aria-activedescendant={active >= 0 && options[active] ? `${ids}-folder-${active}` : undefined}
          value={path}
          placeholder={workspace ? `${withSlash(workspace.path)}…` : ""}
          autoComplete="off"
          spellCheck={false}
          disabled={disabled}
          onChange={(event) => {
            onPath(event.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => {
            // Also before the workspace is known: a focus that comes first lists its
            // subfolders once it is, and until then nothing is asked (no parent).
            if (empty) setOpen(true);
          }}
          onBlur={() => setOpen(false)}
          onKeyDown={(event) => {
            if (options.length === 0) return;
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              const step = event.key === "ArrowDown" ? 1 : -1;
              setActive((at) => (at + step + options.length) % options.length);
            } else if (event.key === "Enter" && active >= 0) {
              event.preventDefault();
              pick(options[active]);
            } else if (event.key === "Escape") {
              event.preventDefault();
              setOpen(false);
            }
          }}
        />
        {options.length > 0 && (
          <ul id={`${ids}-folders`} role="listbox" aria-label="Folders" className="where-list">
            {options.map((one, i) => (
              <li
                key={one}
                id={`${ids}-folder-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(event) => {
                  event.preventDefault(); // keep the input's focus
                  pick(one);
                }}
              >
                {one}/
              </li>
            ))}
          </ul>
        )}
      </div>
      {made && !disabled && (
        <div className="recent">
          Workspace:
          <button
            type="button"
            className="chip-button"
            onClick={() => {
              onPath(withSlash(made));
              input.current?.focus(); // the list's keys and its closing on blur are the field's
              setOpen(true);
            }}
          >
            {made}
          </button>
        </div>
      )}
      {recent.length > 0 && !disabled && (
        <div className="recent">
          Recent:
          {recent.map((one) => (
            <button key={one.path} type="button" className="chip-button" onClick={() => onPath(one.path)}>
              {one.path}
            </button>
          ))}
        </div>
      )}
      {folder?.ok && (
        <span className="field-note ok">
          ✓ git repository{folder.branch ? ` · branch ${folder.branch}` : ""}
        </span>
      )}
      {folder?.ok && folder.warning && <span className="field-note warn">⚠ {folder.warning}</span>}
      {folder && !folder.ok && (
        <div className="field-note bad">
          <div>{folder.problem}</div>
          {folder.scratch ? (
            // In place of LAD-5's command: a new or empty folder takes no file into a commit.
            <div className="folder-hint">
              <div className="muted">
                {folder.problem_kind === "missing"
                  ? "LADO can make this folder and start it from scratch."
                  : "The folder is empty: LADO can start it from scratch."}
              </div>
              <div className="folder-hint-command">
                <button type="button" className="chip-button" disabled={disabled} onClick={() => onScratch(folder.path)}>
                  Start from scratch here
                </button>
              </div>
            </div>
          ) : (
            <>
              {folder.project && (
                <div className="folder-hint">
                  <div className="folder-hint-command">
                    <button
                      type="button"
                      className="chip-button"
                      disabled={disabled}
                      onClick={() => onProject(folder.project!)}
                    >
                      {`${folder.project.repo ? "Start in" : "Open"} the project ${folder.project.title ?? folder.project.id}`}
                    </button>
                  </div>
                </div>
              )}
              {folder.hint && <FolderHint text={folder.hint.text} command={folder.hint.command} />}
            </>
          )}
        </div>
      )}
      {problem && <span className="field-note bad">{problem}</span>}
      {checking && !problem && <span className="field-note">checking…</span>}
    </div>
  );
}

// Where a session's folder comes from: a new one made from scratch, one there is, a clone
// of a git URL, or a project's repository.
function SourceSwitch({
  source,
  onSource,
  disabled,
}: {
  source: Source;
  onSource: (source: Source) => void;
  disabled: boolean;
}) {
  return (
    <span className="segments" role="group" aria-label="Source">
      <button type="button" aria-pressed={source === "scratch"} disabled={disabled} onClick={() => onSource("scratch")}>
        From scratch
      </button>
      <button type="button" aria-pressed={source === "folder"} disabled={disabled} onClick={() => onSource("folder")}>
        Folder
      </button>
      <button type="button" aria-pressed={source === "url"} disabled={disabled} onClick={() => onSource("url")}>
        Clone from URL
      </button>
      <button type="button" aria-pressed={source === "project"} disabled={disabled} onClick={() => onSource("project")}>
        Project
      </button>
    </span>
  );
}

// From scratch's first field: the name in the human's words, what LADO makes of it (the
// folder's and the session's name, the title), and why git cannot sign its commit yet.
function ScratchNameField({
  text,
  onText,
  target,
  problem,
  head,
  disabled,
}: {
  text: string;
  onText: (text: string) => void;
  target: ScratchTarget | null;
  problem: string | null; // the server's refusal of the request itself
  head: ReactNode;
  disabled: boolean;
}) {
  const ids = useId();
  const name = target?.name;
  return (
    <div className="field launch-where">
      <div className="where-head">
        <label htmlFor={`${ids}-scratch-name`}>Name</label>
        {head}
      </div>
      <input
        id={`${ids}-scratch-name`}
        className="launch-words"
        value={text}
        placeholder="Coffee shop site"
        autoComplete="off"
        disabled={disabled}
        onChange={(event) => onText(event.target.value)}
      />
      {text.trim() !== "" && target?.problem && <span className="field-note bad">{target.problem}</span>}
      {name && (
        <span className="field-note">
          folder and session: <b>{name}</b>
          {target.title ? ` · title: ${target.title}` : ""}
        </span>
      )}
      {name && target.name_state && (
        <NameHint folder={{ default_name: name, name_state: target.name_state }} disabled onResume={() => {}} />
      )}
      {target?.author && (
        <div className="field-note bad">
          <div>{target.author.text}</div>
          {target.author.hint && <FolderHint text={target.author.hint.text} command={target.author.hint.command} />}
        </div>
      )}
      {problem && <span className="field-note bad">{problem}</span>}
    </div>
  );
}

function UrlField({
  url,
  onUrl,
  listing,
  remote,
  failed,
  head,
  disabled,
}: {
  url: string;
  onUrl: (url: string) => void;
  listing: boolean;
  remote: RemoteInfo | null;
  failed: { error: string; detail?: unknown } | null;
  head: ReactNode;
  disabled: boolean;
}) {
  const ids = useId();
  const why = failed ? cloneRefused(failed.detail) : null;
  return (
    <div className="field launch-where">
      <div className="where-head">
        <label htmlFor={`${ids}-url`}>Where</label>
        {head}
      </div>
      <input
        id={`${ids}-url`}
        value={url}
        placeholder="git@github.com:owner/repo.git or https://…"
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        onChange={(event) => onUrl(event.target.value)}
      />
      {listing && <span className="field-note">checking the repository…</span>}
      {remote && (
        <span className="field-note ok">
          ✓ repository found · {remote.branches.length} branch{remote.branches.length === 1 ? "" : "es"}
        </span>
      )}
      {failed && (
        <div className="field-note bad">
          <div>{why?.message ?? failed.error}</div>
          {why?.hint && <FolderHint text={why.hint.text} command={why.hint.command} />}
        </div>
      )}
    </div>
  );
}

// The clone's folder as the core finds it; another repository's clone or a clone of this
// one are told under the fields, in full.
function TargetNote({ target, problem }: { target: CloneTarget | null; problem: string | null }) {
  if (problem) return <span className="field-note bad">{problem}</span>;
  if (target === null || target.state === "same_repo" || target.state === "other_repo") return null;
  if (CAN_CLONE.has(target.state)) return <span className="field-note ok">✓ {target.text}</span>;
  return <RefusedNote text={target.text} hint={target.hint ?? null} />;
}

// A folder that takes no clone or fresh start, with what to do instead when the core says
// it (a folder inside a project: its session's command).
function RefusedNote({ text, hint }: { text: string; hint: FolderInfo["hint"] }) {
  if (!hint) return <span className="field-note bad">{text}</span>;
  return (
    <div className="field-note bad">
      <div>{text}</div>
      <FolderHint text={hint.text} command={hint.command} />
    </div>
  );
}

function BranchField({
  remote,
  failed,
  branch,
  onBranch,
  disabled,
}: {
  remote: RemoteInfo | null;
  failed: boolean;
  branch: string | null;
  onBranch: (branch: string) => void;
  disabled: boolean;
}) {
  const ids = useId();
  const label = (one: string) => (one === remote?.default ? `${one} (default)` : one);
  return (
    <div className="field">
      <label htmlFor={`${ids}-branch`}>Branch</label>
      {remote && remote.branches.length > BRANCH_LIST ? (
        <BranchCombo id={`${ids}-branch`} remote={remote} branch={branch} onBranch={onBranch} disabled={disabled} />
      ) : (
        <select
          id={`${ids}-branch`}
          value={remote ? (branch ?? "") : ""}
          disabled={disabled || remote === null}
          onChange={(event) => onBranch(event.target.value)}
        >
          {remote === null ? (
            <option value="">{failed ? "—" : "fetching branches…"}</option>
          ) : (
            remote.branches.map((one) => (
              <option key={one} value={one}>
                {label(one)}
              </option>
            ))
          )}
        </select>
      )}
      {remote && branch === remote.default && <span className="field-note">the repository's default branch</span>}
    </div>
  );
}

// A long branch list: a field that lists the branches holding what is typed.
function BranchCombo({
  id,
  remote,
  branch,
  onBranch,
  disabled,
}: {
  id: string;
  remote: RemoteInfo;
  branch: string | null;
  onBranch: (branch: string) => void;
  disabled: boolean;
}) {
  const [typed, setTyped] = useState<string | null>(null); // null: the branch chosen
  const [active, setActive] = useState(-1);
  const shown = typed ?? branch ?? "";
  const options = typed === null ? [] : remote.branches.filter((one) => one.includes(typed) && one !== typed);
  const pick = (one: string) => {
    onBranch(one);
    setTyped(null);
    setActive(-1);
  };
  return (
    <div className="where-box">
      <input
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={options.length > 0}
        aria-controls={`${id}-list`}
        aria-activedescendant={active >= 0 && options[active] ? `${id}-option-${active}` : undefined}
        value={shown}
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        onChange={(event) => {
          setTyped(event.target.value);
          setActive(-1);
          if (remote.branches.includes(event.target.value)) onBranch(event.target.value);
        }}
        onBlur={() => setTyped(null)}
        onKeyDown={(event) => {
          // Enter while typing picks the branch typed, or the one highlighted; text that is
          // no branch never submits the form with another branch than it shows.
          if (event.key === "Enter" && typed !== null) {
            event.preventDefault();
            if (active >= 0 && options[active]) pick(options[active]);
            else if (remote.branches.includes(typed)) pick(typed);
            return;
          }
          if (options.length === 0) return;
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const step = event.key === "ArrowDown" ? 1 : -1;
            setActive((at) => (at + step + options.length) % options.length);
          } else if (event.key === "Escape") {
            event.preventDefault();
            setTyped(null);
          }
        }}
      />
      {options.length > 0 && (
        <ul id={`${id}-list`} role="listbox" aria-label="Branches" className="where-list">
          {options.map((one, i) => (
            <li
              key={one}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(event) => {
                event.preventDefault(); // keep the input's focus
                pick(one);
              }}
            >
              {one === remote.default ? `${one} (default)` : one}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CloneProgress({ job }: { job: CloneJob }) {
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

// What the human can do about the folder (the core's hint): its sentence, then its command
// to copy. When no copy works, the command is selected to copy by hand.
function FolderHint({ text, command }: { text: string; command: string }) {
  const { note, copy } = useCopy();
  const [byHand, setByHand] = useState(false);
  const code = useRef<HTMLElement>(null);
  const onCopy = async () => {
    const done = await copy(command, "Command copied");
    setByHand(!done);
    if (!done && code.current) window.getSelection()?.selectAllChildren(code.current);
  };
  return (
    <div className="folder-hint">
      <div className="muted">{text}</div>
      <div className="folder-hint-command">
        <code ref={code}>{command}</code>
        <button type="button" className="chip-button" aria-label="Copy command" onClick={onCopy}>
          Copy
        </button>
      </div>
      <span role="status" className="muted">
        {note || (byHand ? "Press ⌘C / Ctrl+C to copy" : "")}
      </span>
    </div>
  );
}

function NameHint({
  folder,
  disabled,
  onResume,
}: {
  folder: Pick<FolderInfo, "default_name" | "name_state">;
  disabled: boolean;
  onResume: () => void;
}) {
  const name = folder.default_name;
  if (folder.name_state === "running") return <span className="field-note">"{name}" is taken by a running session</span>;
  if (folder.name_state === "taken_elsewhere") {
    return <span className="field-note">"{name}" is taken by a session of another folder</span>;
  }
  if (folder.name_state === "stopped_here") {
    return (
      <span className="field-note">
        a stopped session {name} exists for this folder{" "}
        <button type="button" className="link-button" disabled={disabled} onClick={onResume}>
          Resume it
        </button>
      </span>
    );
  }
  return null;
}

function KitsField({
  root,
  listed,
  kits,
  disabled,
  fromLast,
  onKits,
}: {
  root: string | null;
  listed: Asked<KitInfo[]>;
  kits: string[];
  disabled: boolean;
  fromLast: boolean;
  onKits: (kits: string[]) => void;
}) {
  const id = useId();
  const known = valueOf(listed) ?? [];
  const others = known.filter((one) => !kits.includes(one.name));
  return (
    <div className="field">
      <span id={id} className="field-label">
        Kits
      </span>
      <div role="group" aria-labelledby={id} className="kits-box">
        {kits.map((name) => {
          const info = known.find((one) => one.name === name);
          return (
            <span key={name} className={`kits-box-chip${info && !info.valid ? " invalid" : ""}`} title={info?.problem ?? undefined}>
              <span>{name}</span>
              {info?.version && <span className="muted"> {info.version}</span>}
              <button
                type="button"
                aria-label={`Remove ${name}`}
                disabled={disabled}
                onClick={() => onKits(kits.filter((one) => one !== name))}
              >
                ×
              </button>
            </span>
          );
        })}
        {others.length > 0 && (
          <select
            aria-label="Add kit"
            className="add-kit"
            value=""
            disabled={disabled}
            onChange={(event) => event.target.value && onKits([...kits, event.target.value])}
          >
            <option value="">+ Add kit</option>
            {others.map((one) => (
              <option key={one.name} value={one.name} disabled={!one.valid}>
                {one.valid
                  ? `${one.name}${one.version ? ` ${one.version}` : ""}`
                  : `${one.name} · invalid: run lado kits check ${one.name}`}
              </option>
            ))}
          </select>
        )}
      </div>
      {kits.length === 0 && <span className="field-note bad">a session needs at least one kit</span>}
      {listed !== null && "error" in listed && <span className="field-note warn">{listed.error}</span>}
      {fromLast && <span className="field-note">from the last session of this folder</span>}
      {root === null && listed === null && <span className="field-note">checking…</span>}
    </div>
  );
}

function ProviderNote({
  asked,
  info,
  chosen,
}: {
  asked: Asked<ProviderInfo[]>;
  info: ProviderInfo | null;
  chosen: string | null;
}) {
  if (asked !== null && "error" in asked) return <span className="field-note bad">{asked.error}</span>;
  if (asked === null) return <span className="field-note">checking the agent CLIs…</span>;
  if (info === null) return chosen ? <span className="field-note bad">unknown provider {chosen}</span> : null;
  if (!info.installed) return <span className="field-note bad">{`${info.detail}; ${info.install_hint}`}</span>;
  if (info.warning) return <span className="field-note warn">⚠ {info.warning}</span>;
  return null;
}
