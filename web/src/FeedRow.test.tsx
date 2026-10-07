// A row of the session's feed: the avatar, the head, a row that continues a group.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { clock } from "./ChatText";
import { AVATAR_COLOURS, avatar, FeedRow } from "./FeedRow";

afterEach(cleanup);

test("an avatar is the name's first letter, capital, and a colour that depends on the name alone", () => {
  expect(avatar("supervisor")).toEqual(avatar("supervisor"));
  expect(avatar("supervisor").letter).toBe("S");
  expect(avatar("w1").letter).toBe("W");
  const names = ["supervisor", "developer", "reviewer", "w1", "w2", "architect", "checker", "designer"];
  const colours = names.map((name) => avatar(name).colour);
  for (const colour of colours) expect(colour >= 1 && colour <= AVATAR_COLOURS).toBe(true);
  expect(new Set(colours).size).toBeGreaterThan(2); // the names do not all fall on one colour
});

const at = "2026-10-04T17:53:00.000Z";

test("a row has its avatar, the name, the muted part and the time in a <time>", () => {
  render(
    <FeedRow kind="agent" who="supervisor" aside="→ w1" at={at} label="Message from supervisor" id="message-3">
      <p>hello</p>
    </FeedRow>,
  );
  const row = screen.getByRole("article", { name: "Message from supervisor" });
  expect(row.id).toBe("message-3");
  expect(row.querySelector(".avatar")?.textContent).toBe("S");
  expect(row.querySelector(".avatar")?.className).toContain(`avatar-${avatar("supervisor").colour}`);
  expect(row.querySelector(".feed-who")?.textContent).toBe("supervisor");
  expect(within(row).getByText("→ w1")).toBeTruthy();
  expect(row.querySelector("time")?.getAttribute("dateTime")).toBe(at);
  expect(row.querySelector("time")?.textContent).toBe(clock(at));
  expect(within(row).getByText("hello")).toBeTruthy();
});

test("the human's row is You on the action colour; a gate's row has a flag, also for an agent named gate", () => {
  render(
    <>
      <FeedRow kind="human" who="You" at={at} label="Message from you">
        <p>hi</p>
      </FeedRow>
      <FeedRow kind="gate" who="Gate #4" at={at} label="Gate #4">
        <p>ship?</p>
      </FeedRow>
      <FeedRow kind="agent" who="gate" at={at} label="Message from gate">
        <p>an agent</p>
      </FeedRow>
    </>,
  );
  const mine = screen.getByRole("article", { name: "Message from you" });
  expect(mine.className).toContain("mine");
  expect(mine.querySelector(".avatar")?.className).toContain("avatar-human");
  expect(mine.querySelector(".avatar")?.textContent).toBe("Y");
  const gate = screen.getByRole("article", { name: "Gate #4" });
  expect(gate.querySelector(".avatar")?.className).toContain("avatar-gate");
  expect(gate.querySelector(".avatar svg")).toBeTruthy();
  const agent = screen.getByRole("article", { name: "Message from gate" });
  expect(agent.querySelector(".avatar")?.textContent).toBe("G");
  expect(agent.querySelector(".avatar")?.className).not.toContain("avatar-gate");
});

test("a row that continues a group has no head and no letter, but keeps its time", () => {
  render(
    <FeedRow kind="agent" who="supervisor" at={at} label="Message from supervisor" continued>
      <p>more</p>
    </FeedRow>,
  );
  const row = screen.getByRole("article", { name: "Message from supervisor" });
  expect(row.className).toContain("continued");
  expect(row.querySelector(".feed-head")).toBeNull();
  expect(row.querySelector(".avatar")).toBeNull();
  expect(row.querySelector("time")?.getAttribute("dateTime")).toBe(at);
});
