// Usage statistics (docs/design/ui.md, Usage statistics): the banner that asks once, under
// the top bar on every page, Settings → Usage statistics, and the System panel's row. The
// choice is the server's (LADO_HOME), the same as `lado telemetry on|off`; it is read once
// per page and after the page's own choice, not from the change feed.
import { useEffect, useId, useState } from "react";

import {
  ApiError,
  chooseTelemetry,
  getTelemetry,
  getTelemetryPreview,
  type TelemetryInfo,
  type TelemetryPreview,
} from "./api";
import { clock, day } from "./ChatText";
import { useLive } from "./live";

export const TELEMETRY_DOCS = "https://github.com/ladohq/lado/blob/main/docs/telemetry.md";

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

// The day and time of the last send: "today 09:12", "yesterday 09:12", else "12 Oct".
export function sentWhen(iso: string, now = new Date()): string {
  const at = new Date(iso);
  const midnight = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const days = Math.round((midnight(now) - midnight(at)) / 86_400_000);
  if (days === 0) return `today ${clock(iso)}`;
  if (days === 1) return `yesterday ${clock(iso)}`;
  return day(iso);
}

// The System panel's row.
export function statisticsLine(info: TelemetryInfo, now = new Date()): string {
  if (info.off_by) return `off: ${info.off_by}`;
  if (!info.endpoint) return "off: no endpoint";
  if (info.choice === "off") return "off";
  if (info.choice !== "on") return "not chosen";
  return info.last_sent ? `sending · last ${sentWhen(info.last_sent, now)}` : "sending · not sent yet";
}

// Read once `ready` (the banner: once the event stream is open, as the update check).
function useTelemetry(ready = true) {
  const [info, setInfo] = useState<TelemetryInfo | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  useEffect(() => {
    if (!ready) return;
    let current = true;
    getTelemetry().then(
      (found) => current && setInfo(found),
      (error: unknown) => current && setProblem(messageOf(error)),
    );
    return () => {
      current = false;
    };
  }, [ready]);
  return [info, setInfo, problem] as const;
}

// What the next report sends, loaded once when first shown.
function Preview() {
  const [preview, setPreview] = useState<TelemetryPreview | { error: string } | null>(null);
  useEffect(() => {
    let current = true;
    getTelemetryPreview().then(
      (found) => current && setPreview(found),
      (error: unknown) => current && setPreview({ error: messageOf(error) }),
    );
    return () => {
      current = false;
    };
  }, []);
  if (preview === null) return <p className="muted">Loading…</p>;
  if ("error" in preview) return <p className="problem">{preview.error}</p>;
  return (
    <pre className="log">
      {[preview.report, ...preview.errors].map((event) => JSON.stringify(event, null, 2)).join("\n")}
    </pre>
  );
}

function WhatIsSent({ label }: { label: string }) {
  const [shown, setShown] = useState(false);
  return (
    <details className="stats-what" onToggle={(event) => event.currentTarget.open && setShown(true)}>
      <summary>{label}</summary>
      {shown && <Preview />}
    </details>
  );
}

// Under the top bar on every page, while the choice is not made.
export function StatisticsBanner() {
  const { link } = useLive();
  return <StatisticsQuestion ready={link === "open"} />;
}

export function StatisticsQuestion({ ready }: { ready: boolean }) {
  const [info, setInfo] = useTelemetry(ready);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (info?.ask !== true) return null;
  const choose = async (choice: "on" | "off") => {
    setBusy(true);
    setProblem(null);
    try {
      setInfo(await chooseTelemetry(choice));
    } catch (error) {
      setProblem(messageOf(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="update-banner stats-banner" aria-label="Usage statistics">
      <strong>Help improve LADO?</strong>
      {info.new_fields.length > 0 && <p>LADO now also sends: {info.new_fields.join(", ")}.</p>}
      <p>
        Send anonymous usage statistics and LADO's own errors to its maintainers: the LADO version, your OS, the
        agent CLIs and daily counts of sessions, agents and runs; for an error, its type and where in LADO it
        happened. Never paths, repository or session names, messages, prompts or keys.
      </p>
      <p className="muted">
        Nothing is sent until you choose. You can change it any time in Settings or with{" "}
        <code>lado telemetry off</code>.
      </p>
      <WhatIsSent label="What is sent" />
      <div className="stats-buttons">
        <button type="button" className="primary" disabled={busy} onClick={() => void choose("on")}>
          Send statistics
        </button>
        <button type="button" className="quiet" disabled={busy} onClick={() => void choose("off")}>
          Don't send
        </button>
        <a className="stats-doc" href={TELEMETRY_DOCS} target="_blank" rel="noreferrer">
          What LADO collects ↗
        </a>
      </div>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
    </section>
  );
}

const CHOICES = [
  { value: "on", label: "Send" },
  { value: "off", label: "Don't send" },
] as const;

export function StatisticsSetting() {
  const id = useId();
  const [info, setInfo, unread] = useTelemetry();
  const [problem, setProblem] = useState<string | null>(null);
  const locked = info === null || info.off_by !== null || !info.endpoint;
  const tag =
    info === null
      ? null
      : info.off_by
        ? "switched off by the environment"
        : !info.endpoint
          ? "no statistics endpoint"
          : info.choice === null
            ? "not chosen yet"
            : null;
  const checked = info?.off_by ? "off" : info?.choice;
  const choose = async (choice: "on" | "off") => {
    setProblem(null);
    try {
      setInfo(await chooseTelemetry(choice));
    } catch (error) {
      setProblem(messageOf(error));
    }
  };
  return (
    <section className="setting" aria-labelledby={id}>
      <h2 id={id}>
        Usage statistics{tag && <span className="muted stats-tag"> — {tag}</span>}
      </h2>
      <fieldset className="choice" disabled={locked}>
        <legend>Send anonymous statistics and errors to LADO's maintainers</legend>
        <div className="segments">
          {CHOICES.map((option) => (
            <label key={option.value}>
              <input
                type="radio"
                name="statistics"
                value={option.value}
                checked={checked === option.value}
                onChange={() => void choose(option.value)}
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      {unread ? <p className="problem">{unread}</p> : <StatisticsState info={info} />}
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
    </section>
  );
}

function StatisticsState({ info }: { info: TelemetryInfo | null }) {
  const docs = (
    <a href={TELEMETRY_DOCS} target="_blank" rel="noreferrer">
      What LADO collects ↗
    </a>
  );
  if (info === null) return <p className="muted">Loading…</p>;
  if (info.off_by) {
    return (
      <p className="muted">
        Off: <code>{info.off_by}</code> is set in the LADO server's environment.
      </p>
    );
  }
  if (!info.endpoint) return <p className="muted">This LADO has no statistics endpoint: nothing is sent.</p>;
  if (info.choice === null) return <p className="muted">Not chosen yet: nothing is sent. {docs}</p>;
  const about = (
    <p className="muted">
      Anonymous: an ID made at random on this machine, never linked to you. Sent once a day and when LADO itself
      fails, to PostHog in the EU. <code>DO_NOT_TRACK=1</code> or <code>LADO_TELEMETRY=0</code> switch it off.
    </p>
  );
  if (info.choice === "off") {
    return (
      <>
        {about}
        <p>Nothing is sent · {docs}</p>
      </>
    );
  }
  const sent = info.last_sent ? sentWhen(info.last_sent) : null;
  return (
    <>
      {about}
      <p>
        {sent ? `Last sent ${sent.replace(/^(today|yesterday) /, "$1 at ")}` : "Not sent yet"} · {docs}
      </p>
      {info.last_error && <p className="muted">Last try failed: {info.last_error}</p>}
      <WhatIsSent label="What the next report sends" />
    </>
  );
}
