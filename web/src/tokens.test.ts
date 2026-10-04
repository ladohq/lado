import { expect, test } from "vitest";

import tokens from "./tokens.css?raw";

const stylesheets = import.meta.glob<string>("./**/*.css", {
  query: "?raw",
  import: "default",
  eager: true,
});

const COLOUR = /#[0-9a-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|oklch)\(/i;

test("colours are written only in tokens.css; every other stylesheet uses the tokens", () => {
  const others = Object.entries(stylesheets).filter(([path]) => !path.endsWith("/tokens.css"));
  expect(others.length).toBeGreaterThan(0);
  for (const [path, css] of others) {
    const line = css.split("\n").find((l) => COLOUR.test(l));
    expect(line, `${path} has a colour of its own`).toBeUndefined();
  }
});

// Each colour token is light-dark(<light>, <dark>): one line per token for both themes.
function palette(theme: 0 | 1): Record<string, string> {
  const found: Record<string, string> = {};
  for (const [, name, light, dark] of tokens.matchAll(
    /--([\w-]+):\s*light-dark\((#[0-9a-f]{6}),\s*(#[0-9a-f]{6})\)/gi,
  )) {
    found[name] = theme === 0 ? light : dark;
  }
  return found;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// Text and its grounds: ink, muted text and actions on the page, on panels and on the
// current item, a button's label, what waits for the human on its own ground, and a
// dangerous action on panels and on the page (Forget in a session's head).
const PAIRS = [
  ["ink", "ground"],
  ["ink", "panel"],
  ["muted", "ground"],
  ["muted", "panel"],
  ["action", "ground"],
  ["action", "panel"],
  ["ink", "raised"],
  ["muted", "raised"],
  ["on-action", "action"],
  ["human", "human-ground"],
  ["danger", "panel"],
  ["danger", "ground"],
  ["on-danger", "danger"],
  ["term-ink", "term-ground"],
] as const;

test.each([
  ["light", 0],
  ["dark", 1],
] as const)("%s text has a contrast of at least 4.5:1", (_, theme) => {
  const colours = palette(theme);
  for (const [text, ground] of PAIRS) {
    expect(colours[text], text).toBeDefined();
    expect(colours[ground], ground).toBeDefined();
    expect(contrast(colours[text], colours[ground]), `${text} on ${ground}`).toBeGreaterThanOrEqual(
      4.5,
    );
  }
});
