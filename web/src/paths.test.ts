import { expect, test } from "vitest";

import { agentClisPath, DOCS_URL, GENERAL_PATH, GITHUB, MODEL_SERVERS_PATH, STATISTICS_PATH } from "./paths";

test("Agent CLIs' page, and a CLI's row on it by its name", () => {
  expect(agentClisPath()).toBe("/settings/agent-clis");
  expect(agentClisPath("claude")).toBe("/settings/agent-clis#claude");
  expect(agentClisPath("my cli/2")).toBe("/settings/agent-clis#my%20cli%2F2");
});

test("Settings' other pages and Help's links", () => {
  expect(GENERAL_PATH).toBe("/settings/general");
  expect(MODEL_SERVERS_PATH).toBe("/settings/model-servers");
  expect(STATISTICS_PATH).toBe("/settings/statistics");
  expect(DOCS_URL).toBe("https://github.com/ladohq/lado#readme");
  expect(GITHUB).toBe("https://github.com/ladohq/lado");
});
