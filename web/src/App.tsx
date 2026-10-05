// The UI's addresses (docs/design/ui.md, Structure), all inside the shell.
import { Navigate, Route, Routes } from "react-router";

import { Kits } from "./Kits";
import { NeedsYou } from "./NeedsYou";
import { Home, NotFound, Projects } from "./pages";
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
          <Route path=":name/:tab/:item" element={<Session />} />
        </Route>
        <Route path="projects" element={<Projects />} />
        <Route path="kits/:tab?" element={<Kits />} />
        {/* The Marketplace page of earlier versions is the Kits page now. */}
        <Route path="marketplace" element={<Navigate to="/kits" replace />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
