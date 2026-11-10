// New session's Team (docs/design/ui.md, Launch and session control): the session's settings
// as one line (kits, agent, permissions in the agent CLI's own words, a model off the
// default), and Change, which opens the fields: Agent, Kits, Permissions, Model and Switch
// off. The session's name stands beside Task (Launch.tsx). The window holds their
// values; this file shows and edits them.
import type { ReactNode, RefObject } from "react";
import { useId } from "react";

import type { KitInfo, ModeWordsInfo, ProviderInfo } from "./api";
import { InfoTip } from "./InfoTip";

export const DEFAULT_MODE = "default"; // also "no mode given": the provider's own default

// Its agents need the login it lacks for every model it can start on: no saved model of a
// server lets them start without it (ProviderInfo.starts_on_server).
export const cannotStart = (info: ProviderInfo) => info.login_missing && !info.starts_on_server;

// A provider's modes in its own words (Provider.mode_words), none without a provider.
export const modeWords = (info: ProviderInfo | null): ModeWordsInfo[] => info?.mode_words ?? [];

const KITS_ABOUT = "Kits add roles, skills and ways of working to the team. Install more on the Kits page.";
const SWITCH_OFF_ABOUT = "kind:name or kind:name@kit, separated by commas; kinds: agent, skill, mcp, flow.";

// "agent:reviewer@kit-a" as the button that switches it off says it.
const switchOffLabel = (item: string) => {
  const [, rest = item] = item.split(/:(.*)/);
  const [name, kit] = rest.split("@");
  return kit ? `Switch off ${name} of ${kit}` : `Switch off ${name}`;
};

export type TeamRefs = {
  agent: RefObject<HTMLSelectElement | null>;
  kits: RefObject<HTMLSelectElement | null>;
};

export function LaunchTeam({
  open,
  onOpen,
  about,
  // the summary's model part (useLaunchModel's peek), shown off the CLI's default only
  modelPeek,
  kits,
  onKits,
  known,
  kitsError,
  providers,
  providersNote,
  chosen,
  info,
  onProvider,
  agentNote,
  mode,
  onMode,
  modeNote,
  modelField,
  without,
  onWithout,
  switchOff,
  disabled,
  refs,
}: {
  open: boolean;
  onOpen: (open: boolean) => void;
  about: string;
  modelPeek: ReactNode;
  kits: string[];
  onKits: (kits: string[]) => void;
  known: KitInfo[];
  kitsError: string | null;
  providers: ProviderInfo[] | null; // null: asking
  providersNote: ReactNode; // checking, a refusal or a warning of the agent CLI
  chosen: string | null;
  info: ProviderInfo | null;
  onProvider: (name: string) => void;
  agentNote: ReactNode;
  mode: string;
  onMode: (mode: string) => void;
  modeNote: string | null;
  modelField: ReactNode;
  without: string;
  onWithout: (text: string) => void;
  switchOff: string[]; // what a refusal offers to switch off
  disabled: boolean;
  refs: TeamRefs;
}) {
  const ids = useId();
  const words = modeWords(info);
  const chosenWords = words.find((one) => one.value === mode) ?? null;
  const agentName = chosen === null ? "choose…" : (info?.title ?? chosen);
  const others = known.filter((one) => !kits.includes(one.name));
  const described = kits.map((one) => known.find((kit) => kit.name === one)).filter((kit) => kit?.description);
  const listed = new Set(without.split(/[\s,]+/).filter(Boolean));
  return (
    <section className={`launch-team${open ? " open" : ""}`} aria-labelledby={`${ids}-team`}>
      <div className="team-head">
        <span className="field-label" id={`${ids}-team`}>
          Team <InfoTip about="Team">{about}</InfoTip>
        </span>
        {!open && (
          <p className="team-sum">
            <span>
              <span className="k">Kits</span> {kits.length ? kits.join(", ") : "none"}
            </span>
            <span>
              <span className="k">Agent</span> {agentName}
            </span>
            {words.length > 0 && (
              <span>
                <span className="k">Permissions</span> {chosenWords?.summary ?? mode}
              </span>
            )}
            {modelPeek}
          </p>
        )}
        <button
          type="button"
          className="team-change"
          aria-expanded={open}
          aria-controls={`${ids}-body`}
          onClick={() => onOpen(!open)}
        >
          {open ? "Hide" : "Change"}
        </button>
      </div>
      <div id={`${ids}-body`} className="team-body" hidden={!open}>
        <div className="field">
          <label htmlFor={`${ids}-agent`}>Agent</label>
          <select
            ref={refs.agent}
            id={`${ids}-agent`}
            value={providers ? (chosen ?? "") : ""}
            disabled={disabled || providers === null}
            aria-describedby={agentNote || providersNote ? `${ids}-agent-note` : undefined}
            onChange={(event) => onProvider(event.target.value)}
          >
            {providers === null ? (
              <option value="">checking…</option>
            ) : (
              <>
                {chosen === null && (
                  <option value="" disabled>
                    choose…
                  </option>
                )}
                {/* A chosen name the list lacks (a resumed session's) gets its own option,
                    or the select would show the first one, and picking it would be no change. */}
                {chosen !== null && info === null && (
                  <option value={chosen} disabled>
                    {`${chosen} · unknown`}
                  </option>
                )}
                {providers.map((one) => (
                  <option key={one.name} value={one.name} disabled={!one.installed || cannotStart(one)}>
                    {!one.installed
                      ? `${one.title} · not installed`
                      : cannotStart(one)
                        ? `${one.title} · not logged in`
                        : one.login_missing
                          ? `${`${one.title} ${one.version}`.trim()} · not logged in: your server's models only`
                          : `${one.title} ${one.version}`.trim()}
                  </option>
                ))}
              </>
            )}
          </select>
          {(agentNote || providersNote) && (
            <div id={`${ids}-agent-note`} className="place-notes">
              {providersNote}
              {agentNote}
            </div>
          )}
        </div>
        <div className="field launch-wide">
          <span id={`${ids}-kits`} className="field-label">
            Kits{" "}
            <InfoTip about="Kits">
              <span className="info-line">{KITS_ABOUT}</span>
              {described.map((kit) => (
                <span key={kit!.name} className="info-line">{`${kit!.name}: ${kit!.description}`}</span>
              ))}
            </InfoTip>
          </span>
          <div role="group" aria-labelledby={`${ids}-kits`} className="kits-box">
            {kits.map((kitName) => {
              const kit = known.find((one) => one.name === kitName);
              return (
                <span
                  key={kitName}
                  className={`kits-box-chip${kit && !kit.valid ? " invalid" : ""}`}
                  title={kit?.problem ?? undefined}
                >
                  <span>{kitName}</span>
                  {kit?.version && <span className="muted"> {kit.version}</span>}
                  <button
                    type="button"
                    aria-label={`Remove ${kitName}`}
                    disabled={disabled}
                    onClick={() => onKits(kits.filter((one) => one !== kitName))}
                  >
                    ×
                  </button>
                </span>
              );
            })}
            {others.length > 0 && (
              <select
                ref={refs.kits}
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
          {kitsError && <span className="field-note warn">{kitsError}</span>}
        </div>
        <fieldset className="field launch-wide team-modes">
          <legend className="field-label">
            Permissions{" "}
            {words.some((one) => one.description) && (
              <InfoTip about="Permissions">
                <dl>
                  {words.map((one) => (
                    <div key={one.value} className="info-pair">
                      <dt>{one.title}</dt>
                      <dd>
                        {one.description} <code>{one.value}</code>
                      </dd>
                    </div>
                  ))}
                </dl>
              </InfoTip>
            )}
          </legend>
          {words.length === 0 ? (
            <span className="field-note">No permission modes.</span>
          ) : (
            <ul className="mode-list">
              {words.map((one) => {
                const on = one.value === mode;
                return (
                  <li key={one.value} className={`${on ? "on" : ""}${one.risky ? " risk" : ""}`}>
                    <label>
                      <input
                        type="radio"
                        name={`${ids}-mode`}
                        value={one.value}
                        checked={on}
                        disabled={disabled}
                        onChange={() => onMode(one.value)}
                      />
                      <span className="mode-title">{one.title}</span>
                      {one.description && (on || one.risky) && <span className="mode-text">{one.description}</span>}
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          {modeNote && <span className="field-note">{modeNote}</span>}
        </fieldset>
        {modelField}
        <div className="field launch-wide">
          <span className="field-label">
            <label htmlFor={`${ids}-without`}>Switch off</label> <InfoTip about="Switch off">{SWITCH_OFF_ABOUT}</InfoTip>
          </span>
          <input
            id={`${ids}-without`}
            value={without}
            disabled={disabled}
            placeholder="agent:reviewer@kit-b, skill:style"
            onChange={(event) => onWithout(event.target.value)}
          />
          {switchOff.length > 0 && (
            <div className="team-offers">
              {switchOff.map((item) => (
                <button
                  key={item}
                  type="button"
                  className="quiet"
                  disabled={disabled || listed.has(item)}
                  onClick={() => onWithout([...listed, item].join(", "))}
                >
                  {switchOffLabel(item)}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
