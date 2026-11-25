// The first-run guide in the shell (docs/design/ui.md, First-run guide): one GET /api/guide per
// page load, once the change feed is open (as the statistics banner asks), and the engine
// (Guide.tsx, a lazy chunk) loaded only while the server lets it start by itself (no
// LADO_GUIDE=0) and something is left to show, or after Help → Getting started, which
// restarts the guide for this page load whatever the switch says.
import { Component, lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react";

import { getGuide, postGuide, type GuideInfo } from "../api";
import { useLive } from "../live";
import { onRestart } from "./facts";
import { leftToShow } from "./hints";

const Guide = lazy(() => import("./Guide"));

export function GuideMount() {
  const { link } = useLive();
  const [info, setInfo] = useState<GuideInfo | null>(null);
  const [restarts, setRestarts] = useState(0); // Help → Getting started in this page load
  const asked = useRef(false);
  useEffect(() => {
    if (link !== "open" || asked.current) return;
    asked.current = true;
    getGuide().then(setInfo, () => {}); // no guide on a page the server cannot answer
  }, [link]);
  useEffect(
    () =>
      onRestart(() => {
        postGuide({ action: "restart" }).then(
          (found) => {
            setInfo(found);
            setRestarts((n) => n + 1);
          },
          () => {},
        );
      }),
    [],
  );
  if (!info || !(restarts > 0 || (info.auto && leftToShow(info)))) return null;
  return (
    <Contained>
      <Suspense fallback={null}>
        <Guide
          key={restarts}
          info={info}
          restarted={restarts > 0}
          onInfo={(change) => setInfo((now) => (now ? change(now) : now))}
        />
      </Suspense>
    </Contained>
  );
}

// What fails in the guide (its chunk gone after `lado update` in a tab opened before) costs
// the guide only: it draws nothing for the rest of the page load and says why in the console,
// while the page goes on.
class Contained extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("The first-run guide could not load; the page goes on without it.", error);
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}
