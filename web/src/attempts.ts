// Actions that got no answer (docs/design/ui.md, A lost connection): one store for the whole
// tab, held by the live store, so an action's error survives a change of page and shows the
// same wherever its item shows. An attempt keeps how to look at the outcome and how to repeat
// the action; the panels only show it. It is settled by what the server says, never by the
// connection coming back: reached, it ends; not, the human gets Retry.
import {
  ApiError,
  getGates,
  getMessages,
  getSessions,
  getWaiting,
  HUMAN,
  Unreached,
  type MessageInfo,
} from "./api";

export const LOOK_EVERY_MS = 3000; // between looks that could not read the state

// reached: the action arrived; missed: it did not; gone: nothing is left to act on.
export type Outcome = "reached" | "missed" | "gone";

// What a place gives for its action.
export type Action = {
  what: string; // its noun in the error: "<what> not confirmed", "<what> not delivered"
  repeat: () => Promise<unknown>; // sends it again as it was pressed
  look: () => Promise<Outcome>;
  closed: (refusal: string) => boolean; // a refusal of Retry that means the item is closed
  reached: () => void; // the owner's work once it arrived, after the first press
};

// unknown: the outcome is not known yet; missed: not delivered, Retry waits; refused: a Retry
// the server refused, shown as any refusal.
export type AttemptState = "unknown" | "missed" | { refused: string };
export type Attempt = Action & { key: string; state: AttemptState };

export const gateAttempt = (session: string, id: number) => `gate:${session}:${id}`;
export const questionsAttempt = (session: string, agent: string) => `questions:${session}:${agent}`;
export const sendAttempt = (session: string, to: string) => `send:${session}:${to}`;
export const stopAttempt = (session: string) => `stop:${session}`;
export const resumeAttempt = (session: string) => `resume:${session}`;

export class Attempts {
  private all: Record<string, Attempt> = {};
  private looking = new Set<Attempt>();
  private repeating = new Set<Attempt>();
  private timer: ReturnType<typeof setTimeout> | undefined;

  constructor(
    private publish: (all: Record<string, Attempt>) => void,
    private feedOpen: () => boolean,
  ) {}

  private put(all: Record<string, Attempt>) {
    this.all = all;
    this.publish(all);
  }

  // Whether it still stands: another press replaces it, and each change makes a new one.
  private stands(attempt: Attempt) {
    return this.all[attempt.key] === attempt;
  }

  private change(attempt: Attempt, state: AttemptState) {
    const changed = { ...attempt, state };
    this.put({ ...this.all, [attempt.key]: changed });
    return changed;
  }

  clear(key: string) {
    if (!(key in this.all)) return;
    const { [key]: _, ...others } = this.all;
    this.put(others);
  }

  // The action's first press: true when it was answered, false when it got no answer and
  // is kept here; a refusal goes to the caller, as any refusal does.
  async send(key: string, action: Action): Promise<boolean> {
    try {
      await action.repeat();
      return true;
    } catch (error) {
      if (!(error instanceof Unreached)) throw error;
    }
    const attempt: Attempt = { ...action, key, state: "unknown" };
    this.put({ ...this.all, [key]: attempt });
    void this.lookAt(attempt);
    return false;
  }

  // Each action whose outcome is not known, now: when one is made and when the feed opens,
  // then every LOOK_EVERY_MS while the feed is open.
  look() {
    Object.values(this.all).forEach((attempt) => void this.lookAt(attempt));
  }

  private async lookAt(attempt: Attempt) {
    if (attempt.state !== "unknown" || this.looking.has(attempt) || this.repeating.has(attempt)) return;
    this.looking.add(attempt);
    const outcome = await attempt.look().catch((error: unknown) => {
      // The session's own lists answer 404 once it is forgotten.
      return error instanceof ApiError && error.status === 404 ? ("gone" as const) : null;
    });
    this.looking.delete(attempt);
    // Replaced meanwhile, or Retry took over: this look says nothing about it.
    if (this.stands(attempt) && !this.repeating.has(attempt)) {
      if (outcome === "reached") {
        this.clear(attempt.key);
        attempt.reached();
      } else if (outcome === "gone") {
        this.clear(attempt.key);
      } else if (outcome === "missed") {
        this.change(attempt, "missed");
      }
    }
    this.schedule();
  }

  private schedule() {
    const waiting = Object.values(this.all).some((one) => one.state === "unknown");
    if (!waiting || this.timer !== undefined || !this.feedOpen()) return;
    this.timer = setTimeout(() => {
      this.timer = undefined;
      this.look();
    }, LOOK_EVERY_MS);
  }

  // Retry: what was pressed, again. A refusal that says the item is closed counts as reached.
  async retry(key: string) {
    const found = this.all[key];
    if (!found) return;
    const attempt = this.change(found, "unknown");
    this.repeating.add(attempt);
    const refusal = await attempt.repeat().then(
      () => null,
      (error: unknown) => error,
    );
    this.repeating.delete(attempt);
    if (refusal instanceof Unreached) {
      void this.lookAt(attempt);
      return;
    }
    const text = refusal === null ? null : refusal instanceof ApiError ? refusal.message : String(refusal);
    if (text === null || attempt.closed(text)) {
      this.clear(key);
      attempt.reached();
    } else {
      this.change(attempt, { refused: text });
    }
  }

  stop() {
    clearTimeout(this.timer);
    this.timer = undefined;
  }
}

// What a refusal of each kind's Retry says when its item is closed: the core's words, pinned
// on both sides by closedRefusals.cases.json.
export const closedBy = {
  gate: (text: string) => /^gate #\d+ is closed already/.test(text),
  questions: (text: string) => /^question #\d+ is (answered|dismissed|closed|stopped|gone)$/.test(text),
  stop: (text: string) => / is stopped already/.test(text),
  resume: (text: string) => / is already running/.test(text),
};

const sameNames = (message: MessageInfo, names: string[]) => {
  const got = message.attachments.map((one) => one.full_name).sort();
  const sent = [...names].sort();
  return got.length === sent.length && got.every((name, n) => name === sent[n]);
};

// How each kind reads its outcome. Through the API, not the feed: a resumed stream has no end
// of its replay, so no moment says the lists are current.
export const looks = {
  gate: (session: string, id: number) => async (): Promise<Outcome> => {
    const gate = (await getGates(session)).find((one) => one.id === id);
    return gate && gate.answer === null ? "missed" : "reached";
  },
  // What waits leaves out a stopped session, whose questions are stopped: absent is right.
  questions: (session: string, ids: number[]) => async (): Promise<Outcome> => {
    const items = await getWaiting();
    const open = items.some((one) => one.session === session && one.question && ids.includes(one.question.id));
    return open ? "missed" : "reached";
  },
  // A message of the human to the same agent with the same text and files, after the last
  // one known at the click: ids, as the phone's clock is not the server's. The server keeps
  // the whole text in the body unless the summary is exactly it.
  send: (session: string, to: string, after: number, text: string, names: string[]) => async (): Promise<Outcome> => {
    const { items } = await getMessages(session, { with: "human", after });
    const sent = text.trim();
    const found = items.some(
      (one) =>
        one.from === HUMAN && one.to === to && sameNames(one, names) && (sent === "" || (one.body || one.summary) === sent),
    );
    return found ? "reached" : "missed";
  },
  stop: (session: string) => async (): Promise<Outcome> => {
    const found = (await getSessions()).find((one) => one.name === session);
    return !found || found.status === "stopped" ? "reached" : "missed";
  },
  resume: (session: string) => async (): Promise<Outcome> => {
    const found = (await getSessions()).find((one) => one.name === session);
    if (!found) return "gone";
    return found.status === "running" || found.status === "loop_down" ? "reached" : "missed";
  },
};
