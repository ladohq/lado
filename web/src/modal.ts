// The one way a modal window of the UI opens and closes (docs/design/ui.md, Structure). The
// browser gives the focus back to what had it at showModal() only on close() of a dialog that
// is still in the page, and a window here goes when React removes it: so close() comes from a
// layout effect's cleanup, which runs before the removal; a passive effect's runs after it.
// That cleanup runs within React's commit, when React hears no events: the opener's onFocus
// does not fire, so its Tooltip shows nothing (tests/ui/test_layout.py holds this).
// What a window does at opening beyond this stays in its own effect, which runs after this one.
import { useLayoutEffect, type RefObject } from "react";

export function useModal(dialog: RefObject<HTMLDialogElement | null>) {
  useLayoutEffect(() => {
    const shown = dialog.current; // the ref is empty by the time the window goes
    shown?.showModal();
    return () => shown?.close();
  }, [dialog]);
}
