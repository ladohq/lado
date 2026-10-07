import { expect, test } from "vitest";

import { shortRemote } from "./remote";

test.each([
  ["git@github.com:ladohq/lado.git", "github.com/ladohq/lado"],
  ["git@github.com:ladohq/lado", "github.com/ladohq/lado"],
  ["ssh://git@gitlab.example.com:2222/team/app.git", "gitlab.example.com:2222/team/app"],
  ["https://github.com/ladohq/lado.git", "github.com/ladohq/lado"],
  ["https://github.com/ladohq/lado", "github.com/ladohq/lado"],
  ["/srv/git/lado.git", "/srv/git/lado"],
])("the short form of %s is %s", (url, short) => {
  expect(shortRemote(url)).toBe(short);
});
