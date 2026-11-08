// The set-up panel's own words (LaunchSetup.tsx): sizes, and the by-hand command put together
// from the core's lines (lado.setup.shell_line, setup.MAKE), so a tick rebuilds the same line
// the core would write.
import { expect, test } from "vitest";

import type { LeftOutInfo, SetupInfo } from "./api";
import { refusalText, setupCommand, size } from "./LaunchSetup";

const MAKE = "git init && git add -A && git commit -m 'First commit'";

const setup = (more: Partial<SetupInfo> = {}): SetupInfo => ({
  files: 1,
  bytes: 1,
  left_out: [],
  refusal: null,
  author: null,
  make: MAKE,
  max_files: 20000,
  ...more,
});

const left = (path: string, line: string): LeftOutInfo => ({ path, reason: "secret", size: 1, line });

test("the command is the core's lines of what stays left out, then its make", () => {
  expect(setupCommand(setup(), [left(".env", "/.env"), left("it's.key", `'/it'"'"'s.key'`)])).toBe(
    `printf '%s\\n' /.env '/it'"'"'s.key' >> .gitignore && ${MAKE}`,
  );
  expect(setupCommand(setup(), [])).toBe(MAKE);
});

test("each refusal in the window's words, the limit the core's", () => {
  const refused = (kind: NonNullable<SetupInfo["refusal"]>["kind"], files = 0, line = "") =>
    refusalText(setup({ refusal: { kind, files, bytes: 0, line }, max_files: 3 }));
  expect(refused("home")).toBe("Choose a smaller folder: this is your home folder.");
  expect(refused("too_big", 4)).toBe("Choose a smaller folder: this one holds over 3 files.");
  expect(refused("too_big", 2)).toBe("Choose a smaller folder: this one holds over 2 GB.");
  expect(refused("unreadable", 0, "warning: x")).toBe("Choose another folder: git cannot read all of it (warning: x).");
  expect(refused("odd_name", 0, ".env\\nok")).toBe(
    "Choose another folder, or rename .env\\nok: LADO cannot leave out a name with a line break or bytes that are no text.",
  );
});

test("sizes in a few characters", () => {
  expect(size(512)).toBe("512 B");
  expect(size(4404019)).toBe("4.2 MB");
  expect(size(251658240)).toBe("240 MB");
  expect(size(2 * 1024 ** 3)).toBe("2 GB");
});
