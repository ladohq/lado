import { configure } from "@testing-library/react";

// `waitFor` and `findBy` for the whole suite: a loaded machine missed Testing Library's 1 s, and
// vitest has no setting for it. A test sets no timeout of its own.
configure({ asyncUtilTimeout: 10_000 });

// What jsdom lacks and the components call: a Range has no box there (the head's team measures
// the title's text by one, Team.tsx).
Range.prototype.getBoundingClientRect = () => new DOMRect();
