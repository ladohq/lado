// Needs you (docs/design/ui.md, Structure): what waits for the human in every session not
// stopped, by session, oldest first, live from the feed (live.ts, the list `waiting`): per
// session its waiting card (WaitingCard.tsx), the same as in its chat and answered in place,
// then each agent in `waiting` with why it waits and its terminal. Each session links to its
// chat.
import { useEffect } from "react";
import { Link, useNavigate } from "react-router";

import type { AgentInfo, WaitingItem } from "./api";
import { FeedRow } from "./FeedRow";
import { useLive, useLiveStore } from "./live";
import { NotificationsOffer } from "./Notifications";
import { chatPath, terminalPath } from "./paths";
import { useTitle } from "./Shell";
import { agentWaits } from "./waiting";
import { WaitingCard } from "./WaitingCard";

// The muted part of an agent's row ends so: the row's time is when it began to wait.
const SINCE = "waiting since";

// The items by session, the sessions in the order of their oldest item.
function bySession(items: WaitingItem[]): [string, WaitingItem[]][] {
  const groups = new Map<string, WaitingItem[]>();
  for (const item of items) groups.set(item.session, [...(groups.get(item.session) ?? []), item]);
  return [...groups];
}

export function NeedsYou() {
  useTitle("Needs you");
  const live = useLiveStore();
  const loaded = useLive().waiting;
  useEffect(() => live.watch("waiting"), [live]);

  return (
    <div className="needs-you">
      <NotificationsOffer />
      {loaded === null && <p className="muted">Loading…</p>}
      {loaded && "error" in loaded && (
        <p className="problem" role="alert">
          {loaded.error}
        </p>
      )}
      {loaded && "items" in loaded && loaded.items.length === 0 && <p className="empty">Nothing waits for you</p>}
      {loaded &&
        "items" in loaded &&
        bySession(loaded.items).map(([session, items]) => <SessionWaits key={session} session={session} items={items} />)}
    </div>
  );
}

// A session's name, "In the chat", its waiting card, then its agents waiting in their
// terminal. Its runs are watched for their colours on the card's tabs.
function SessionWaits({ session, items }: { session: string; items: WaitingItem[] }) {
  const live = useLiveStore();
  const runs = useLive().runs[session];
  useEffect(() => live.watch("runs", session), [live, session]);
  const questions = items.flatMap((item) => (item.question ? [item.question] : []));
  const gates = items.flatMap((item) => (item.gate ? [item.gate] : []));
  const agents = items.flatMap((item) => (item.agent ? [{ agent: item.agent, since: item.since }] : []));
  return (
    <section className="waits-session" aria-label={`Session ${session}`}>
      <h2>
        <Link to={chatPath(session)}>{session}</Link>
        <Link className="waits-chat" to={chatPath(session)} aria-label={`${session}'s chat`}>
          In the chat
        </Link>
      </h2>
      <WaitingCard
        session={session}
        questions={questions}
        gates={gates}
        runs={runs && "items" in runs ? runs.items : null}
        stopped={false}
        focus={null}
      />
      {agents.map(({ agent, since }) => (
        <div key={agent.name} className="waits-item">
          <WaitingAgent session={session} agent={agent} since={since} />
        </div>
      ))}
    </section>
  );
}

function WaitingAgent({ session, agent, since }: { session: string; agent: AgentInfo; since: string }) {
  const navigate = useNavigate();
  return (
    <FeedRow kind="agent" who={agent.name} aside={`${agent.role} · ${SINCE}`} at={since} label={`${agent.name} waits`}>
      <div className="waits-agent">
        <p className="waits-reason">{agentWaits(agent)}</p>
        <div className="answer-actions">
          <button
            type="button"
            className="primary"
            aria-label={`Open ${agent.name}'s terminal`}
            onClick={() => navigate(terminalPath(session, agent.name))}
          >
            Open terminal
          </button>
        </div>
      </div>
    </FeedRow>
  );
}
