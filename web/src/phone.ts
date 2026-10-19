// The phone layout (docs/design/ui.md, Phone layout): its one query. A touch screen
// (`pointer: coarse`) no wider than 600 px or no higher than 500 px is a phone; a mouse or a
// trackpad never is, whatever its window, nor a tablet. "tall" upright, "short" sideways.
// The Shell mirrors it to `<html data-phone>`, the key of styles.css's section "Phone
// layout"; components whose structure changes on a phone read usePhone().
import { useEffect, useLayoutEffect, useState } from "react";

export const PHONE_QUERY = "(pointer: coarse) and (max-width: 600px), (pointer: coarse) and (max-height: 500px)";
export const SHORT_QUERY = "(max-height: 500px)";

export type Phone = "tall" | "short" | null;

function phoneNow(): Phone {
  const match = (query: string) => window.matchMedia?.(query).matches ?? false;
  if (!match(PHONE_QUERY)) return null;
  return match(SHORT_QUERY) ? "short" : "tall";
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

// On a phone the app is as high as the part of the window the human sees (LAD-109): the
// visual viewport's height and its offset from the page's top go on <html> as
// `--phone-height` and `--phone-top`, which styles.css's "Phone layout" sizes the app by.
// Safari ignores the viewport's `interactive-widget=resizes-content`: its keyboard covers
// the window's bottom and pans the page instead, so only the visual viewport tells where
// the visible part is. Without one (an old browser) the CSS fallback applies.
export function usePhoneViewport(phone: Phone): void {
  useLayoutEffect(() => {
    const viewport = window.visualViewport;
    if (!phone || !viewport) return;
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
  }, [phone]);
}
