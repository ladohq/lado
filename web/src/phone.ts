// The phone layout (docs/design/ui.md, Phone layout): its one query. A window no wider than
// 600 px is a phone, with a mouse too (LAD-193); so is a touch screen (`pointer: coarse`) no
// higher than 500 px, a phone held sideways. A wider window with a mouse or a trackpad never
// is, however low, nor a tablet or a touch laptop. "tall" upright, "short" sideways.
// The Shell mirrors it to `<html data-phone>`, the key of styles.css's section "Phone
// layout"; components whose structure changes on a phone read usePhone().
import { useEffect, useLayoutEffect, useState } from "react";

export const PHONE_QUERY = "(max-width: 600px), (pointer: coarse) and (max-height: 500px)";
export const SHORT_QUERY = "(max-height: 500px)";
// A tablet: a touch screen where a session's page stands still (styles.css). Its keyboard asks
// for the visible height as a phone's does.
const TABLET_QUERY = "(pointer: coarse) and (min-width: 601px) and (max-width: 900px)";

export type Phone = "tall" | "short" | null;

function phoneNow(): Phone {
  const match = (query: string) => window.matchMedia?.(query).matches ?? false;
  if (!match(PHONE_QUERY)) return null;
  return match(SHORT_QUERY) ? "short" : "tall";
}

// Whether a media query holds now, again when the window changes.
export function useMedia(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia?.(query).matches ?? false);
  useEffect(() => {
    const list = window.matchMedia?.(query);
    const changed = () => setMatches(list?.matches ?? false);
    list?.addEventListener?.("change", changed);
    changed(); // a change between the first render and now
    return () => list?.removeEventListener?.("change", changed);
  }, [query]);
  return matches;
}

// The phone layout now, again when the screen turns or resizes.
export function usePhone(): Phone {
  const [phone, setPhone] = useState(phoneNow);
  useEffect(() => {
    const lists = [PHONE_QUERY, SHORT_QUERY].map((query) => window.matchMedia?.(query)).filter(Boolean);
    const changed = () => setPhone(phoneNow());
    lists.forEach((list) => list?.addEventListener?.("change", changed));
    changed(); // a change between the first render and now
    return () => lists.forEach((list) => list?.removeEventListener?.("change", changed));
  }, []);
  return phone;
}

// On a phone or a tablet the app is as high as the part of the window the human sees (LAD-109):
// the visual viewport's height and its offset from the page's top go on <html> as
// `--phone-height` and `--phone-top`, which styles.css sizes the app by.
// Safari ignores the viewport's `interactive-widget=resizes-content`: its keyboard covers
// the window's bottom and pans the page instead, so only the visual viewport tells where
// the visible part is. Without one (an old browser) the CSS fallback applies.
export function usePhoneViewport(phone: Phone): void {
  const tablet = useMedia(TABLET_QUERY);
  const follows = phone !== null || tablet;
  useLayoutEffect(() => {
    const viewport = window.visualViewport;
    if (!follows || !viewport) return;
    const style = document.documentElement.style;
    const follow = () => {
      style.setProperty("--phone-height", `${viewport.height}px`);
      style.setProperty("--phone-top", `${viewport.offsetTop}px`);
    };
    follow();
    viewport.addEventListener("resize", follow);
    viewport.addEventListener("scroll", follow);
    return () => {
      viewport.removeEventListener("resize", follow);
      viewport.removeEventListener("scroll", follow);
      style.removeProperty("--phone-height");
      style.removeProperty("--phone-top");
    };
  }, [follows]);
}
