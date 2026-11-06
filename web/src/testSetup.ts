// What jsdom lacks and the components call: a Range has no box there (the head's team measures
// the title's text by one, Team.tsx).
Range.prototype.getBoundingClientRect = () => new DOMRect();
