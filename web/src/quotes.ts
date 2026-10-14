// Where a quote goes (docs/design/ui.md, Selected text and copy buttons): to the composer of
// its session mounted on the page (the latest when there are two), else it waits here and
// the page goes to the session's chat, whose composer takes it on mount. The composer's
// text stays its own state; this only hands a quote over.
import { chatPath } from "./paths";
import { withQuote } from "./quote";

type Insert = (quote: string) => void;

const composers = new Map<string, Insert[]>();
const pending = new Map<string, string>(); // a session's quotes, as a composer's text
const listeners = new Map<string, Set<() => void>>();

// A mounted composer of `session`; the function returned unregisters it.
export function registerComposer(session: string, insert: Insert): () => void {
  const list = composers.get(session) ?? [];
  composers.set(session, [...list, insert]);
  return () => {
    const now = (composers.get(session) ?? []).filter((one) => one !== insert);
    if (now.length) composers.set(session, now);
    else composers.delete(session);
  };
}

// The quotes kept for `session`'s next composer, once; null when there are none.
export function takePending(session: string): string | null {
  const text = pending.get(session) ?? null;
  pending.delete(session);
  return text;
}

// Run `listener` on each quote of `session` (the waiting card folds).
export function onQuote(session: string, listener: () => void): () => void {
  const set = listeners.get(session) ?? new Set();
  set.add(listener);
  listeners.set(session, set);
  return () => {
    set.delete(listener);
    if (set.size === 0) listeners.delete(session);
  };
}

export function sendQuote(session: string, quote: string, navigate: (path: string) => void): void {
  listeners.get(session)?.forEach((listener) => listener());
  const mounted = composers.get(session);
  if (mounted?.length) {
    mounted[mounted.length - 1](quote);
    return;
  }
  pending.set(session, withQuote(pending.get(session) ?? "", quote));
  navigate(chatPath(session));
}
