// The set-up panel of a plain folder of files (docs/design/ui.md, Launch and session control;
// lado.setup): what "Set up and start" will save and leave out, the left-out files the human
// may tick in, and the same by hand under "Do it yourself". The counts and the command come
// from the core's preview, each left-out path with its line of the by-hand command; the
// window only adds what is ticked and puts the lines together.
import { useState } from "react";

import type { LeftOutInfo, SetupInfo } from "./api";
import { InfoTip } from "./InfoTip";
import { FolderHint } from "./LaunchWhere";

const SETUP_ABOUT =
  "LADO keeps a history of changes in this folder (git), so you can see and undo what the team does. Your files stay where they are.";

// The size of `bytes` in a few characters: "4.2 MB".
export function size(bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const shown = unit === 0 || value >= 100 ? Math.round(value).toString() : value.toFixed(1).replace(/\.0$/, "");
  return `${shown} ${units[unit]}`;
}

// The by-hand commands leaving out `left`: the core's line of each, then its `make`, as
// lado.setup.command puts them.
export function setupCommand(setup: SetupInfo, left: LeftOutInfo[]): string {
  if (left.length === 0) return setup.make;
  return `printf '%s\\n' ${left.map((one) => one.line).join(" ")} >> .gitignore && ${setup.make}`;
}

// Why a folder may not be set up, in the window's words.
export function refusalText(setup: SetupInfo): string {
  const refusal = setup.refusal!;
  if (refusal.kind === "home") return "Choose a smaller folder: this is your home folder.";
  if (refusal.kind === "unreadable") return `Choose another folder: git cannot read all of it (${refusal.line}).`;
  if (refusal.kind === "odd_name") {
    return `Choose another folder, or rename ${refusal.line}: LADO cannot leave out a name with a line break or bytes that are no text.`;
  }
  return refusal.files > setup.max_files
    ? `Choose a smaller folder: this one holds over ${setup.max_files.toLocaleString("en")} files.`
    : "Choose a smaller folder: this one holds over 2 GB.";
}

const why = (one: LeftOutInfo) =>
  one.reason === "secret"
    ? "looks like a secret"
    : one.reason === "large"
      ? `${size(one.size ?? 0)}, larger than 50 MB`
      : "a separate git repository";

export function LaunchSetup({
  id,
  setup,
  include,
  onInclude,
  onCheckAgain,
  checkingAgain,
}: {
  id: string; // the panel's, Where's aria-describedby
  setup: SetupInfo; // the last answer, while `checkingAgain` the one before the new
  include: string[];
  onInclude: (include: string[]) => void;
  onCheckAgain: () => void;
  checkingAgain: boolean; // the folder is checked again: the author's Check again waits, the rest counts
}) {
  const [shown, setShown] = useState<"review" | "diy" | null>(null); // one disclosure at a time
  if (checkingAgain && !setup.author) {
    return (
      <div id={id} className="setup-panel">
        <p>
          Not yet set up for LADO. <span className="muted" aria-live="polite">Counting files…</span>{" "}
          <InfoTip about="setup">{SETUP_ABOUT}</InfoTip>
        </p>
      </div>
    );
  }
  if (setup.refusal) {
    return (
      <div id={id} className="setup-refuse">
        <p className="field-note bad" role="alert">
          {refusalText(setup)}
        </p>
      </div>
    );
  }
  if (setup.author) {
    const inContainer = setup.author.hint?.text.includes("LADO_GIT_NAME") ?? false;
    return (
      <div id={id} className="setup-refuse">
        <p className="field-note bad" role="alert">
          {inContainer ? setup.author.hint!.text : "Git doesn't know who you are yet. Tell it once for this computer:"}
        </p>
        {setup.author.hint && <FolderHint text="" command={setup.author.hint.command} />}
        {!inContainer && (
          <button type="button" className="quiet" aria-disabled={checkingAgain || undefined} onClick={() => !checkingAgain && onCheckAgain()}>
            {checkingAgain ? "Checking…" : "Check again"}
          </button>
        )}
      </div>
    );
  }
  const taken = setup.left_out.filter((one) => include.includes(one.path));
  const left = setup.left_out.filter((one) => !include.includes(one.path));
  const files = setup.files + taken.length;
  const bytes = setup.bytes + taken.reduce((sum, one) => sum + (one.size ?? 0), 0);
  const toggle = (path: string) =>
    onInclude(include.includes(path) ? include.filter((one) => one !== path) : [...include, path]);
  return (
    <div id={id} className="setup-panel">
      <p>
        Not yet set up for LADO. Starting saves{" "}
        <b aria-live="polite" className="nowrap">{`${files.toLocaleString("en")} file${files === 1 ? "" : "s"} (${size(bytes)})`}</b>{" "}
        as the starting point. <InfoTip about="setup">{SETUP_ABOUT}</InfoTip>
      </p>
      <div className="setup-row">
        {setup.left_out.length > 0 && (
          <button
            type="button"
            className="setup-disc"
            aria-expanded={shown === "review"}
            aria-controls={`${id}-left`}
            onClick={() => setShown(shown === "review" ? null : "review")}
          >
            {`${left.length} left out · Review`}
          </button>
        )}
        <button
          type="button"
          className="setup-disc muted"
          aria-expanded={shown === "diy"}
          aria-controls={`${id}-diy`}
          onClick={() => setShown(shown === "diy" ? null : "diy")}
        >
          Do it yourself
        </button>
      </div>
      {shown === "review" && (
        <>
          <p className="setup-cap">Tick to include:</p>
          <ul id={`${id}-left`} className="setup-left" aria-label="Left out">
            {setup.left_out.map((one, i) => {
              const on = include.includes(one.path);
              const repo = one.reason === "repository";
              return (
                <li key={one.path} className={`${repo ? "off" : ""}${on && one.reason === "secret" ? " on-secret" : ""}`}>
                  <label>
                    <input
                      type="checkbox"
                      aria-label={`Include ${one.path}`}
                      aria-describedby={`${id}-why-${i}${on && one.reason === "secret" ? ` ${id}-warn-${i}` : ""}`}
                      checked={on}
                      disabled={repo}
                      onChange={() => toggle(one.path)}
                    />
                    <span className="setup-txt">
                      <span className="setup-name">{one.path}</span>
                      <span className="muted" id={`${id}-why-${i}`}>
                        {why(one)}
                      </span>
                      {on && one.reason === "secret" && (
                        <span className="setup-warn" id={`${id}-warn-${i}`}>
                          Will be saved in the history.
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </>
      )}
      {shown === "diy" && (
        <div id={`${id}-diy`}>
          <FolderHint text="Run in this folder, then choose it again:" command={setupCommand(setup, left)} />
        </div>
      )}
    </div>
  );
}
