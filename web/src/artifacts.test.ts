// Artifacts in the UI: whether an attachment changed since (the one comparison of hashes) and
// how each media type is shown.
import { expect, test } from "vitest";

import { changed, kindOf } from "./artifacts";
import { artifact, attachment } from "./fakes";

test("an attachment changed since when its artifact's latest record has another hash", () => {
  expect(changed(attachment(), { items: [artifact()] })).toBe("unchanged");
  expect(changed(attachment(), { items: [artifact({}, { id: "r2", hash: "h2" })] })).toBe("changed");
});

test("without the session's artifacts loaded, or without its artifact, nothing is known", () => {
  expect(changed(attachment(), null)).toBe("unknown");
  expect(changed(attachment(), undefined)).toBe("unknown");
  expect(changed(attachment(), { error: "down" })).toBe("unknown");
  expect(changed(attachment(), { items: [artifact({ id: "other" })] })).toBe("unknown");
});

test("each media type is shown as one kind", () => {
  expect(kindOf("text/markdown")).toBe("markdown");
  expect(kindOf("text/plain")).toBe("text");
  expect(kindOf("text/x-python")).toBe("text");
  expect(kindOf("application/json")).toBe("text");
  expect(kindOf("image/png")).toBe("image");
  expect(kindOf("image/svg+xml")).toBe("image");
  expect(kindOf("text/html")).toBe("html");
  expect(kindOf("application/pdf")).toBe("other");
  expect(kindOf("image/tiff")).toBe("other");
});
