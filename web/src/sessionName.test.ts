// The session's name the New session window offers (sessionName.ts): the task's tracker key,
// else the place's name; numbered when taken; a typed name kept with its title.
import { describe, expect, test } from "vitest";

import { autoBase, freeName, nextFree, sessionName, slug } from "./sessionName";
import cases from "./sessionSlug.cases.json";

describe("slug, as the core's runtime.slug", () => {
  test.each(cases.cases)("$text → $slug", ({ text, slug: expected }) => {
    expect(slug(text)).toBe(expected);
  });
});

describe("autoBase", () => {
  test.each([
    ["LAD-263: the codex model must win", "lad-263"],
    ["[LAD-263] the codex model", "lad-263"],
    ["LAD-7", "lad-7"],
    ["LAD-263 Fix the login", "lad-263"],
    ["Fix LAD-263 in the doctor text", "lad-263"],
    ["Fix login\nLAD-263: on the second line", "lad-263"],
    ["Fix LAD-263, then LAD-264", "lad-263"],
    ["(LAD-263) in brackets", "lad-263"],
    ["HTTP-2 support for the proxy", "http-2"],
  ])("%j → %s", (task, base) => {
    expect(autoBase(task, "lado")).toBe(base);
  });

  test.each([
    ["Fix the login redirect after the session expires"],
    ["xLAD-263 glued to a word before"],
    ["LAD-263a glued to a word after"],
    ["lad-263 in small letters"],
    ["L-1 one letter"],
    ["Utf-8 not all capitals"],
    ["Поправить вход"],
    [""],
    ["   \n "],
  ])("no key in %j: the place's name", (task) => {
    expect(autoBase(task, "lado")).toBe("lado");
  });

  test("no key and no place: no name", () => {
    expect(autoBase("", null)).toBeNull();
    expect(autoBase("Fix the login", null)).toBeNull();
  });
});

describe("freeName, as the core's runtime.free_name", () => {
  test("the base when free, else the first free number from 2", () => {
    expect(freeName("lad-263", new Set())).toBe("lad-263");
    expect(freeName("lad-263", new Set(["lad-263"]))).toBe("lad-263-2");
    expect(freeName("lad-263", new Set(["lad-263", "lad-263-2", "lad-263-4"]))).toBe("lad-263-3");
  });
});

describe("nextFree: the name a taken one gives way to", () => {
  test("a numbered name of a taken series goes on with its number", () => {
    expect(nextFree("webapp-2", new Set(["webapp", "webapp-2"]))).toBe("webapp-3");
    expect(nextFree("webapp", new Set(["webapp"]))).toBe("webapp-2");
  });

  test("a number that is part of the name stays", () => {
    expect(nextFree("lad-263", new Set(["lad-263"]))).toBe("lad-263-2");
  });

  test("the name itself counts as taken", () => {
    expect(nextFree("app", new Set())).toBe("app-2");
  });
});

describe("sessionName", () => {
  const base = { task: "", placeBase: "lado", taken: new Set<string>() };

  test("automatic: the task's name, else the place's", () => {
    expect(sessionName({ ...base, mode: "auto", typed: "" })).toEqual({
      id: "lado",
      title: null,
      base: "lado",
      numbered: false,
      taken: false,
    });
    expect(sessionName({ ...base, mode: "auto", typed: "", task: "LAD-263: codex model" }).id).toBe("lad-263");
  });

  test("automatic and taken: numbered", () => {
    const named = sessionName({ ...base, mode: "auto", typed: "", task: "LAD-263: x", taken: new Set(["lad-263"]) });
    expect(named).toEqual({ id: "lad-263-2", title: null, base: "lad-263", numbered: true, taken: false });
  });

  test("automatic without a name", () => {
    expect(sessionName({ ...base, placeBase: null, mode: "auto", typed: "" }).id).toBeNull();
  });

  test("typed: its plain form the name, the text the title", () => {
    expect(sessionName({ ...base, mode: "custom", typed: " Review Kao " })).toEqual({
      id: "review-kao",
      title: "Review Kao",
      base: "review-kao",
      numbered: false,
      taken: false,
    });
  });

  test("typed as a plain name: no title", () => {
    const named = sessionName({ ...base, mode: "custom", typed: "lad-263-docs", task: "Fix the login redirect" });
    expect([named.id, named.title]).toEqual(["lad-263-docs", null]);
  });

  test("typed without a plain form: the automatic name with the text as its title", () => {
    const named = sessionName({ ...base, mode: "custom", typed: "Вход после сессии", task: "Fix LAD-263" });
    expect([named.id, named.title, named.taken]).toEqual(["lad-263", "Вход после сессии", false]);
    expect(sessionName({ ...base, mode: "custom", typed: "Вход x" }).id).toBe("lado");
  });

  test("typed and taken: kept, never numbered", () => {
    const named = sessionName({ ...base, mode: "custom", typed: "review-kao", taken: new Set(["review-kao"]) });
    expect([named.id, named.numbered, named.taken]).toEqual(["review-kao", false, true]);
  });

  test("typed: the task and the place do not change it", () => {
    const named = sessionName({ mode: "custom", typed: "Review Kao", task: "LAD-1: x", placeBase: "webapp", taken: new Set() });
    expect(named.id).toBe("review-kao");
  });
});
