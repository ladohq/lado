// A Settings section's page (docs/design/ui.md, Settings): on a phone "‹ Settings" back to
// the list, then the head, the section's name from the one list (settingsSections.ts) with
// the page's own tools beside it, then the page. Settings.tsx focuses the h2 when the human
// moves to another section.
import { useId, type ReactNode, type Ref } from "react";
import { Link } from "react-router";

import { usePhone } from "./phone";
import { sectionOf, type SectionSlug } from "./settingsSections";

export function SettingsPage(props: {
  slug: SectionSlug;
  tools?: ReactNode;
  className?: string;
  ref?: Ref<HTMLElement>;
  children: ReactNode;
}) {
  const id = useId();
  const phone = usePhone() !== null;
  return (
    <section ref={props.ref} className={`spage${props.className ? ` ${props.className}` : ""}`} aria-labelledby={id}>
      {phone && (
        <Link className="back-link" to="/settings">
          <span aria-hidden="true">‹</span> Settings
        </Link>
      )}
      <div className="spage-head">
        <h2 id={id} tabIndex={-1}>
          {sectionOf(props.slug)?.name}
        </h2>
        {props.tools}
      </div>
      {props.children}
    </section>
  );
}
