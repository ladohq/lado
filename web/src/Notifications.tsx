// Browser notifications (docs/design/ui.md, Notifications): when something new waits for
// the human and the tab is not on the screen, one silent notification per item, tagged by
// its key, so several LADO tabs show one. Off by default; turned on from Needs you or
// Settings, which ask the browser's permission; what the browser refuses is said in words.
// The notifier lives in the shell, so it works on every page.
import { useEffect, useRef, useSyncExternalStore } from "react";
import { Link, useNavigate } from "react-router";

import { useLive, useLiveStore } from "./live";
import { storedNotifications, storeNotifications } from "./prefs";
import { waitingTarget, waitingText } from "./waiting";

const UNSUPPORTED = "This browser cannot show notifications.";
const INSECURE =
  "The browser shows notifications only on a secure page: open LADO at the address lado ui prints (127.0.0.1 or localhost).";
const DENIED =
  "The browser blocks notifications for this page: allow them in the site's settings (the icon left of the address), then turn them on again.";
const DISMISSED = "The browser did not allow notifications: turn them on again and allow them.";

type Support = "ok" | "unsupported" | "insecure";

function support(): Support {
  if (typeof Notification === "undefined") return "unsupported";
  return window.isSecureContext === false ? "insecure" : "ok";
}

// Whether the human turned them on here, and why the last try or notification failed.
type Chosen = { enabled: boolean; failure: string | null };

let chosen: Chosen = { enabled: storedNotifications(), failure: null };
const listeners = new Set<() => void>();

function choose(next: Chosen) {
  chosen = next;
  listeners.forEach((listener) => listener());
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

async function enable() {
  if (support() !== "ok") return choose({ enabled: false, failure: null });
  const answer = Notification.permission === "granted" ? "granted" : await Notification.requestPermission();
  if (answer !== "granted") return choose({ enabled: false, failure: answer === "denied" ? DENIED : DISMISSED });
  storeNotifications(true);
  choose({ enabled: true, failure: null });
}

function disable() {
  storeNotifications(false);
  choose({ enabled: false, failure: null });
}

// Whether they are on (chosen and allowed), and what to tell the human, if anything.
function useNotifications(): { on: boolean; problem: string | null; possible: boolean } {
  const { enabled, failure } = useSyncExternalStore(subscribe, () => chosen);
  // The stored choice is read again on each mount: another tab may have changed it.
  useEffect(() => {
    const stored = storedNotifications();
    if (stored !== chosen.enabled) choose({ ...chosen, enabled: stored });
  }, []);
  const kind = support();
  if (kind === "unsupported") return { on: false, problem: UNSUPPORTED, possible: false };
  if (kind === "insecure") return { on: false, problem: INSECURE, possible: false };
  const allowed = Notification.permission === "granted";
  return {
    on: enabled && allowed,
    problem: failure ?? (enabled && !allowed ? DENIED : null),
    possible: true,
  };
}

// On Needs you: whether they are on, or the button that turns them on.
export function NotificationsOffer() {
  const { on, problem, possible } = useNotifications();
  if (on) {
    return (
      <p className="notify-offer muted">
        Browser notifications are on. <Link to="/settings">Settings</Link>
        {problem && <span className="field-problem"> {problem}</span>}
      </p>
    );
  }
  return (
    <div className="notify-offer">
      <p>Get a browser notification when something new waits for you while this tab is in the background.</p>
      <button type="button" className="primary" disabled={!possible} onClick={() => void enable()}>
        Enable notifications
      </button>
      {problem && <p className="field-problem">{problem}</p>}
    </div>
  );
}

// In Settings: the switch.
export function NotificationsSetting() {
  const { on, problem, possible } = useNotifications();
  return (
    <>
      <label className="switch setting-switch">
        <input
          type="checkbox"
          checked={on}
          disabled={!possible}
          onChange={(event) => void (event.target.checked ? enable() : disable())}
        />
        Browser notifications
      </label>
      <p className="muted">
        One notification for each new thing that waits for you (a gate, a question, an agent), while this tab is in
        the background. A click brings you to it. No sound.
      </p>
      {problem && <p className="field-problem">{problem}</p>}
    </>
  );
}

// In the shell: while they are on, follows what waits and notifies of each new item.
export function Notifier() {
  const { on } = useNotifications();
  return on ? <Notify /> : null;
}

function Notify() {
  const live = useLiveStore();
  const loaded = useLive().waiting;
  const navigate = useNavigate();
  // The keys seen in this tab: those of the first list only remembered, the later new ones
  // notified. Kept across the feed's resets, so what came during a gap is notified.
  const seen = useRef<Set<string> | null>(null);
  const shown = useRef(new Map<string, Notification>());
  useEffect(() => live.watch("waiting"), [live]);

  useEffect(() => {
    if (loaded === null || "error" in loaded) return;
    const keys = new Set(loaded.items.map((item) => item.key));
    shown.current.forEach((notification, key) => {
      if (keys.has(key)) return;
      notification.close(); // answered, here or elsewhere
      shown.current.delete(key);
    });
    if (seen.current === null) {
      seen.current = keys;
      return;
    }
    for (const item of loaded.items) {
      if (seen.current.has(item.key)) continue;
      seen.current.add(item.key);
      if (document.visibilityState === "visible") continue;
      try {
        const notification = new Notification(`LADO · ${item.session}`, {
          body: waitingText(item),
          tag: item.key,
          silent: true,
        });
        notification.onclick = () => {
          window.focus();
          navigate(waitingTarget(item));
          notification.close();
        };
        shown.current.set(item.key, notification);
      } catch (error) {
        choose({ ...chosen, failure: `The browser did not show a notification: ${String(error)}` });
      }
    }
  }, [loaded, navigate]);

  return null;
}
