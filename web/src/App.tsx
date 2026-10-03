// The UI's addresses (docs/design/ui.md, Structure), all inside the shell.
import { Route, Routes } from "react-router";

import { Home, Kits, Marketplace, NeedsYou, NotFound, Projects } from "./pages";
import { NoSession, Session, Sessions } from "./Sessions";
import { Settings } from "./Settings";
import { Shell } from "./Shell";

export function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Home />} />
        <Route path="needs-you" element={<NeedsYou />} />
        <Route path="sessions" element={<Sessions />}>
          <Route index element={<NoSession />} />
          <Route path=":name" element={<Session />} />
          <Route path=":name/:tab" element={<Session />} />
        </Route>
        <Route path="projects" element={<Projects />} />
        <Route path="kits" element={<Kits />} />
        <Route path="marketplace" element={<Marketplace />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
