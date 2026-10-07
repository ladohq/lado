// Needs you (docs/design/ui.md, Structure): what waits for the human in every session not
// stopped, by session, oldest first, live from the feed (live.ts, the list `waiting`): a
// gate's and a question's card answered in place, the same cards as in the chat, and each
// agent in `waiting` with why it waits and its terminal. Each links to its session's chat.
import { useEffect } from "react";
import { Link, useNavigate } from "react-router";

import type { AgentInfo, WaitingItem } from "./api";
import { FeedRow } from "./FeedRow";
import { gateAnchor, GateRow } from "./GateCard";
import { useLive, useLiveStore } from "./live";
import { NotificationsOffer } from "./Notifications";
import { chatPath, terminalPath } from "./paths";
import { messageAnchor, Question } from "./Question";
import { useTitle } from "./Shell";
import { agentWaits } from "./waiting";

// The muted part of each row ends so: the row's time is when it began to wait.
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
        bySession(loaded.items).map(([session, items]) => (
          <section key={session} className="waits-session" aria-label={`Session ${session}`}>
            <h2>
              <Link to={chatPath(session)}>{session}</Link>
            </h2>
            {items.map((item) => (
              <Waits key={item.key} item={item} />
            ))}
          </section>
        ))}
    </div>
  );
}

// Each in the feed's row (FeedRow), as in the chat, with since when it waits.
function Waits({ item }: { item: WaitingItem }) {
  const { session } = item;
  if (item.gate) {
    const { gate } = item;
    return (
      <div className="waits-item">
        <GateRow session={session} gate={gate} stopped={false} aside={`${gate.run} · ${gate.state} · ${SINCE}`} />
        <ChatLink to={chatPath(session, gateAnchor(gate.id))} label={`Gate #${gate.id} in the chat`} />
      </div>
    );
  }
  if (item.question) {
    const { question } = item;
    return (
      <div className="waits-item">
        <FeedRow kind="agent" who={question.from} aside={SINCE} at={question.created_at} label={`Question from ${question.from}`}>
          <Question session={session} question={question} />
        </FeedRow>
        <ChatLink to={chatPath(session, messageAnchor(question.id))} label={`Question #${question.id} in the chat`} />
      </div>
    );
  }
  if (!item.agent) return null;
  return (
    <div className="waits-item">
      <WaitingAgent session={session} agent={item.agent} since={item.since} />
      <ChatLink to={chatPath(session)} label={`${session}'s chat`} />
    </div>
  );
}

function ChatLink({ to, label }: { to: string; label: string }) {
  return (
    <Link className="waits-chat" to={to} aria-label={label}>
      In the chat
    </Link>
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
