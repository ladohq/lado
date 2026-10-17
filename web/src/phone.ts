// The phone layout (docs/design/ui.md, Phone layout): its one query. A touch screen
// (`pointer: coarse`) no wider than 600 px or no higher than 500 px is a phone; a mouse or a
// trackpad never is, whatever its window, nor a tablet. "tall" upright, "short" sideways.
// The Shell mirrors it to `<html data-phone>`, the key of styles.css's section "Phone
// layout"; components whose structure changes on a phone read usePhone().
import { useEffect, useState } from "react";

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
