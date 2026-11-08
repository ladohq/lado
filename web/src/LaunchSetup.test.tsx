// The set-up panel's own words (LaunchSetup.tsx): sizes, and the by-hand command quoted as the
// core quotes it (lado.setup.command, Python's shlex.quote), so a tick rebuilds the same line.
import { expect, test } from "vitest";

import type { SetupInfo } from "./api";
import { ignoreLine, setupCommand, shellQuote, size } from "./LaunchSetup";

const MAKE = "git init && git add -A && git commit -m 'First commit'";

const setup = (command: string): SetupInfo => ({
  files: 1,
  bytes: 1,
  left_out: [],
  refusal: null,
  author: null,
  command,
});

test.each([
  ["notes.txt", "notes.txt"],
  ["my notes.txt", "'my notes.txt'"],
  ["it's", `'it'"'"'s'`],
  ["", "''"],
  ["/a/b-c_d.e@f%g+h=i:j,k", "/a/b-c_d.e@f%g+h=i:j,k"],
  ["$HOME", "'$HOME'"],
])("%j is quoted as shlex.quote quotes it", (word, quoted) => {
  expect(shellQuote(word)).toBe(quoted);
});

test("a left-out path's .gitignore line is anchored and takes git's pattern characters as they are", () => {
  expect(ignoreLine(".env")).toBe("/.env");
  expect(ignoreLine("old/")).toBe("/old/");
  expect(ignoreLine("a*b?[c]\\d")).toBe("/a\\*b\\?\\[c]\\\\d");
  expect(ignoreLine("trailing ")).toBe("/trailing\\ ");
});

test("the command is rebuilt from what stays left out, as the core writes it", () => {
  const core = setup(`printf '%s\\n' /.env /talk.mp4 >> .gitignore && ${MAKE}`);
  expect(setupCommand(core, [{ path: ".env", reason: "secret", size: 1 }, { path: "talk.mp4", reason: "large", size: 2 }])).toBe(
    core.command,
  );
  expect(setupCommand(core, [{ path: "my notes.txt", reason: "large", size: 2 }])).toBe(
    `printf '%s\\n' '/my notes.txt' >> .gitignore && ${MAKE}`,
  );
  expect(setupCommand(core, [])).toBe(MAKE);
  expect(setupCommand(setup(MAKE), [])).toBe(MAKE);
});

test("sizes in a few characters", () => {
  expect(size(512)).toBe("512 B");
  expect(size(4404019)).toBe("4.2 MB");
  expect(size(251658240)).toBe("240 MB");
  expect(size(2 * 1024 ** 3)).toBe("2 GB");
});
