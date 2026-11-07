/// <reference types="node" />
import { readFileSync } from "node:fs";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The package's version, the one source of it: the bundle compares it with the server's.
function ladoVersion(): string {
  const pyproject = readFileSync(new URL("../pyproject.toml", import.meta.url), "utf8");
  const project = /^\[project\]$([\s\S]*?)(?=^\[|(?![\s\S]))/m.exec(pyproject)?.[1] ?? "";
  const version = /^version\s*=\s*"([^"]+)"/m.exec(project)?.[1];
  if (!version) throw new Error("no [project] version in ../pyproject.toml");
  return version;
}

// The bundle goes into the Python package: the wheel ships it, users need no Node.
export default defineConfig({
  plugins: [react()],
  define: { __LADO_VERSION__: JSON.stringify(ladoVersion()) },
  build: {
    outDir: "../src/lado/server/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 800, // xterm.js is about 300 kB of it

  },
  test: {
    environment: "jsdom",
    setupFiles: ["src/testSetup.ts"],
    css: true, // tokens.test.ts reads the stylesheets (?raw); left out, they are empty
    // The UI formats and sorts in the human's locale; the tests expect en-US's on any machine.
    env: { LC_ALL: "en_US.UTF-8" },
    // A loaded machine took tests over vitest's 5 s; a green run is no slower for it.
    testTimeout: 30_000,
  },
});
