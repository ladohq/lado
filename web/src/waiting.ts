// What waits for the human (WaitingItem, from /api/waiting): where it is answered and how it
// is named, the same on Needs you and in a notification.
import type { AgentInfo, WaitingItem } from "./api";
import { gateAnchor } from "./GateCard";
import { chatPath, terminalPath } from "./paths";
import { messageAnchor } from "./Question";

// An agent waiting with no reason LADO knows waits on a prompt in its terminal.
export const IN_TERMINAL = "waits for you in its terminal";

export const agentWaits = (agent: AgentInfo) => agent.waiting_reason ?? IN_TERMINAL;

// Where the human answers it: a card in its session's chat, or the agent's terminal.
export function waitingTarget(item: WaitingItem): string {
  if (item.gate) return chatPath(item.session, gateAnchor(item.gate.id));
  if (item.question) return chatPath(item.session, messageAnchor(item.question.id));
  if (item.agent) return terminalPath(item.session, item.agent.name);
  return chatPath(item.session);
}

// One line on what waits: the gate's or the agent's question, or why the agent waits.
export function waitingText(item: WaitingItem): string {
  if (item.gate) return item.gate.question;
  if (item.question) return item.question.summary;
  if (item.agent) {
    const why = item.agent.waiting_reason;
    return why ? `${item.agent.name} waits: ${why}` : `${item.agent.name} ${IN_TERMINAL}`;
  }
  return "";
}
