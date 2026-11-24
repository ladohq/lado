// A project's commit author (docs/design/ui.md, Projects): one line under the project's facts.
// Without an author of its own, who its repositories' agents commit as and from where (the
// author most of them share, then each repository that differs) and a quiet `Set one for this
// project`; with nobody anywhere, a warning and a link to LADO's author in Settings; with one,
// the author with Edit and Remove (Undo), as on Settings → Git servers. The form, its
// refusals and the result line are Settings' (AuthorForm).
import { useEffect, useRef, useState } from "react";

import {
  type CommitAuthor,
  clearProjectAuthor,
  type ProjectInfo,
  refusalOf,
  setProjectAuthor,
} from "./api";
import { authorText, SETTINGS_AUTHOR } from "./AuthorMissing";
import { AuthorForm, VariablesWin } from "./GitServers";
import { InfoTip } from "./InfoTip";

const TIP =
  "Agents of this project sign their commits with this author in every repository of the project, over LADO's author and a git server's. Most projects need none.";

const SOURCE: Record<string, string> = {
  lado: "(LADO's)",
  git: "(from git on this computer)",
  server: "(its git server's)",
};

type Line = { tone: "ok" | "bad"; text: string; undo?: { name: string; email: string } };

const keyOf = (found: CommitAuthor | null | undefined) =>
  found?.author ? `${found.source} ${authorText(found.author)}` : "none";

// Who signs, with its source in muted words after it.
function Signer({ found }: { found: CommitAuthor }) {
  if (!found.author) return <span className="w">nobody</span>;
  return (
    <>
      <b>{authorText(found.author)}</b> <span className="ca-src">{SOURCE[found.source] ?? ""}</span>
    </>
  );
}

export function ProjectAuthor({ project, onChanged }: { project: ProjectInfo; onChanged: (project: ProjectInfo) => void }) {
  const title = project.title ?? project.id;
  const [form, setForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [line, setLine] = useState<Line | null>(null);
  const edit = useRef<HTMLButtonElement>(null);
  const undo = useRef<HTMLButtonElement>(null);
  const [focus, setFocus] = useState<{ on: "edit" | "undo"; n: number } | null>(null);
  useEffect(() => {
    if (focus) (focus.on === "edit" ? edit : undo).current?.focus();
  }, [focus]);
  const focusOn = (on: "edit" | "undo") => setFocus((now) => ({ on, n: (now?.n ?? 0) + 1 }));
  const actions = useRef(0);
  const act = () => {
    setLine(null);
    return ++actions.current;
  };
  const change = async (call: () => Promise<ProjectInfo>, done: Line, keep = false) => {
    if (busy) return;
    const mine = keep ? ++actions.current : act();
    setBusy(true);
    try {
      onChanged(await call());
      if (mine !== actions.current) return;
      setLine(done);
      focusOn(done.undo ? "undo" : "edit");
    } catch (error) {
      if (mine === actions.current) setLine({ tone: "bad", text: refusalOf(error).message });
    } finally {
      setBusy(false);
    }
  };
  const own = project.author ?? null;
  const repos = project.repos.filter((repo) => repo.commit_author);
  // The author most repositories share, else the one a new repository gets.
  const counts = new Map<string, number>();
  for (const repo of repos) counts.set(keyOf(repo.commit_author), (counts.get(keyOf(repo.commit_author)) ?? 0) + 1);
  const most = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  const main = (most ? repos.find((repo) => keyOf(repo.commit_author) === most)?.commit_author : null) ?? project.commit_author ?? null;
  const others = repos.filter((repo) => keyOf(repo.commit_author) !== keyOf(main));
  const nobody = !main?.author && others.every((repo) => !repo.commit_author!.author);
  const opener = (
    <button
      ref={edit}
      type="button"
      className="link-button"
      aria-label={`Set a commit author for ${title}`}
      aria-pressed={form}
      disabled={busy}
      onClick={() => {
        act();
        setForm((now) => !now);
      }}
    >
      Set one for this project
    </button>
  );
  return (
    <div className="project-author">
      <p className="pa-line">
        <span className="pa-label">Commit author</span>
        <InfoTip about="the project's commit author">{TIP}</InfoTip>{" "}
        {own ? (
          <>
            <b>{authorText(own)}</b> <span className="ca-src">(this project's, in every repository)</span>
          </>
        ) : nobody ? (
          <>
            <span className="w">⚠ Nobody to commit as: agents cannot commit.</span>{" "}
            <a
              className="link-like"
              href={SETTINGS_AUTHOR}
              target="_blank"
              rel="noopener"
              aria-label="Set LADO's author in Settings (opens a new tab)"
            >
              Set LADO's author in Settings ↗
            </a>{" "}
            <span className="sep">·</span> {opener}
          </>
        ) : (
          <>
            {main && <Signer found={main} />}
            {others.map((repo) => (
              <span key={repo.name}>
                {"; in "}
                <b>{repo.name}</b>
                {": "}
                <Signer found={repo.commit_author!} />
              </span>
            ))}{" "}
            <span className="sep">·</span> {opener}
          </>
        )}
      </p>
      {own && (
        <span className="pa-acts">
          <button
            ref={edit}
            type="button"
            className="quiet"
            aria-label={`Edit the commit author of ${title}`}
            aria-pressed={form}
            disabled={busy}
            onClick={() => {
              act();
              setForm((now) => !now);
            }}
          >
            Edit
          </button>
          <button
            type="button"
            className="quiet"
            aria-label={`Remove the commit author of ${title}`}
            disabled={busy}
            onClick={() => {
              setForm(false);
              void change(() => clearProjectAuthor(project.id), { tone: "ok", text: "Author removed.", undo: own });
            }}
          >
            Remove
          </button>
        </span>
      )}
      {form && (
        <AuthorForm
          saved={own}
          save={(name, email) => setProjectAuthor(project.id, name, email)}
          onTouch={act}
          onCancel={() => {
            act();
            setForm(false);
            focusOn("edit");
          }}
          onDone={(done, mine) => {
            onChanged(done);
            setForm(false);
            if (mine !== actions.current) return;
            setLine({ tone: "ok", text: "Author saved." });
            focusOn("edit");
          }}
        />
      )}
      {line && (
        <p className={`gx-result ${line.tone}`} role={line.tone === "ok" ? "status" : "alert"}>
          <span className="t">{line.text}</span>
          {line.undo && (
            <button
              ref={undo}
              type="button"
              className="quiet"
              aria-label={`Undo the removal of the commit author of ${title}`}
              disabled={busy}
              onClick={() =>
                void change(() => setProjectAuthor(project.id, line.undo!.name, line.undo!.email), { tone: "ok", text: "Author saved." }, true)
              }
            >
              Undo
            </button>
          )}
        </p>
      )}
      <VariablesWin names={project.author_variables ?? []} />
    </div>
  );
}
