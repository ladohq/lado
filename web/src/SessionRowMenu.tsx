// A session list row's menu (docs/design/ui.md, Launch and session control): actions on the
// entry only, and only ones that work: Copy link and Open in new tab. The session's own
// actions are in its head (SessionControl.tsx). The link is the page's address without the
// token: the login is the browser's cookie. The ⋯, its copy and its note are RowMenu.tsx's.
import { sessionLink, sessionPath } from "./paths";
import { RowMenu } from "./RowMenu";

export function SessionRowMenu({ name }: { name: string }) {
  return (
    <RowMenu
      name={name}
      items={[
        {
          label: "Copy link",
          copy: sessionLink(name),
          copied: "Link copied",
          field: { title: `Link to ${name}`, label: "Link" },
        },
        { label: "Open in new tab", href: sessionPath(name) },
      ]}
    />
  );
}
