// A project's variables and secrets (openspec change projects-section): set, edit or
// replace, remove, the core's refusals, the marks, and a secret's value kept out of
// everything but its request's body.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ProjectInfo } from "./api";
import { FakeProjects, project } from "./projectFakes";
import { ProjectVariables } from "./ProjectVariables";

let server: FakeProjects;

function Page({ start }: { start: ProjectInfo }) {
  const [shown, setShown] = useState(start);
  return <ProjectVariables project={shown} onChanged={setShown} />;
}

function open(start: ProjectInfo = server.projects.shop) {
  return render(<Page start={start} />);
}

const LIKE_SECRET =
  "STRIPE_KEY looks like a secret (KEY): a plain variable takes no name with TOKEN, KEY, SECRET or " +
  "PASSWORD; set it as a secret with lado project set shop STRIPE_KEY --secret";

beforeEach(() => {
  server = new FakeProjects({
    shop: project("shop", { title: "Shop", variables: [{ name: "BOARD_URL", value: "https://a" }], secrets: ["GH_TOKEN"] }),
  });
  server.refuse = ({ method, path, body }) => {
    if (method === "PUT" && path.endsWith("/variables/STRIPE_KEY")) return LIKE_SECRET;
    if (method === "PUT" && path.includes("/secrets/") && body && (body as { value: string }).value === "") {
      const name = path.split("/").pop();
      return `the secret ${name} is empty; to remove it: lado project unset shop ${name}`;
    }
    if (method === "PUT" && path.endsWith("/secrets/BOARD_URL")) {
      return "BOARD_URL is a plain variable of shop; remove it first with lado project unset shop BOARD_URL";
    }
    return null;
  };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const variables = () => screen.getByRole("region", { name: "Variables" });
const secrets = () => screen.getByRole("region", { name: "Secrets" });
const button = (where: HTMLElement, name: string) => within(where).getByRole("button", { name });
const row = (where: HTMLElement, name: string) => within(where).getByText(name).closest("tr") as HTMLElement;
const secretField = () => secrets().querySelector<HTMLInputElement>("input[type=password]")!;

// Plain variables

test("a variable is added, edited in place and listed by name", async () => {
  open();
  fireEvent.click(button(variables(), "+ Add variable"));
  fireEvent.change(within(variables()).getByRole("textbox", { name: "Name" }), { target: { value: "API_URL" } });
  fireEvent.change(within(variables()).getByRole("textbox", { name: "Value" }), { target: { value: "https://x" } });
  fireEvent.click(button(variables(), "Add"));
  await waitFor(() => expect(within(variables()).getByText("API_URL")).toBeTruthy());
  expect(server.calls("PUT", "/api/projects/shop/variables/API_URL")[0].body).toEqual({ value: "https://x" });
  const names = [...variables().querySelectorAll("td.project-name")].map((cell) => cell.textContent);
  expect(names).toEqual(["API_URL", "BOARD_URL"]);

  fireEvent.click(button(row(variables(), "BOARD_URL"), "Edit"));
  const value = within(variables()).getByRole("textbox", { name: "Value of BOARD_URL" });
  expect((value as HTMLInputElement).value).toBe("https://a");
  fireEvent.change(value, { target: { value: "https://b" } });
  fireEvent.click(button(variables(), "Save"));
  await waitFor(() => expect(within(variables()).getByText("https://b")).toBeTruthy());
});

test("a name that looks like a secret is refused verbatim and offered as a secret", async () => {
  open();
  fireEvent.click(button(variables(), "+ Add variable"));
  fireEvent.change(within(variables()).getByRole("textbox", { name: "Name" }), { target: { value: "STRIPE_KEY" } });
  fireEvent.change(within(variables()).getByRole("textbox", { name: "Value" }), { target: { value: "sk_test_1" } });
  fireEvent.click(button(variables(), "Add"));
  expect(await within(variables()).findByText(LIKE_SECRET)).toBeTruthy();
  // The fields are kept for the human to fix.
  expect((within(variables()).getByRole("textbox", { name: "Name" }) as HTMLInputElement).value).toBe("STRIPE_KEY");
  fireEvent.click(button(variables(), "Add STRIPE_KEY as a secret instead"));
  expect(within(variables()).queryByRole("textbox", { name: "Name" })).toBeNull();
  expect((within(secrets()).getByRole("textbox", { name: "Name" }) as HTMLInputElement).value).toBe("STRIPE_KEY");
  expect(secretField().value).toBe("");
  const inputs = [...document.querySelectorAll("input")].map((one) => one.value);
  expect(inputs).not.toContain("sk_test_1");
});

test("removing a variable asks in its row; Cancel sends nothing", async () => {
  open();
  fireEvent.click(button(row(variables(), "BOARD_URL"), "Remove"));
  expect(variables().textContent).toContain("Remove BOARD_URL?");
  fireEvent.click(button(variables(), "Cancel"));
  expect(server.asked.filter((one) => one.method === "DELETE")).toEqual([]);
  fireEvent.click(button(row(variables(), "BOARD_URL"), "Remove"));
  fireEvent.click(button(variables(), "Remove"));
  await waitFor(() => expect(within(variables()).queryByText("BOARD_URL")).toBeNull());
  expect(server.calls("DELETE", "/api/projects/shop/variables/BOARD_URL")).toHaveLength(1);
});

// Secrets

test("a secret is added in a hidden field, shown as set · hidden, the field emptied", async () => {
  open();
  fireEvent.click(button(secrets(), "+ Add secret"));
  const field = secretField();
  expect(field.getAttribute("autocomplete")).toBe("off");
  expect(field.getAttribute("placeholder")).toBe("value (not shown after saving)");
  expect(field.closest("form")).toBeNull();
  fireEvent.change(within(secrets()).getByRole("textbox", { name: "Name" }), { target: { value: "API_KEY" } });
  fireEvent.change(field, { target: { value: "canary-add-1" } });
  fireEvent.click(button(secrets(), "Add"));
  await waitFor(() => expect(within(secrets()).getByText("API_KEY")).toBeTruthy());
  expect(server.calls("PUT", "/api/projects/shop/secrets/API_KEY")[0].body).toEqual({ value: "canary-add-1" });
  expect(field.value).toBe("");
  expect(row(secrets(), "API_KEY").textContent).toContain("set · hidden");
  expect(document.body.innerHTML).not.toContain("canary-add-1");
});

test("Enter in the value field adds the secret", async () => {
  open();
  fireEvent.click(button(secrets(), "+ Add secret"));
  fireEvent.change(within(secrets()).getByRole("textbox", { name: "Name" }), { target: { value: "API_KEY" } });
  fireEvent.change(secretField(), { target: { value: "canary-enter" } });
  fireEvent.keyDown(secretField(), { key: "Enter" });
  await waitFor(() => expect(within(secrets()).getByText("API_KEY")).toBeTruthy());
});

test("a refused secret keeps its value in the open field; Cancel empties it", async () => {
  open();
  fireEvent.click(button(secrets(), "+ Add secret"));
  fireEvent.change(within(secrets()).getByRole("textbox", { name: "Name" }), { target: { value: "BOARD_URL" } });
  const field = secretField();
  fireEvent.change(field, { target: { value: "canary-kept" } });
  fireEvent.click(button(secrets(), "Add"));
  expect(
    await within(secrets()).findByText(
      "BOARD_URL is a plain variable of shop; remove it first with lado project unset shop BOARD_URL",
    ),
  ).toBeTruthy();
  expect(field.value).toBe("canary-kept");
  fireEvent.click(button(secrets(), "Cancel"));
  expect(field.value).toBe("");
  fireEvent.click(button(secrets(), "+ Add secret"));
  expect(secretField().value).toBe("");
});

test("an empty secret is the core's refusal", async () => {
  open();
  fireEvent.click(button(secrets(), "+ Add secret"));
  fireEvent.change(within(secrets()).getByRole("textbox", { name: "Name" }), { target: { value: "OPENAI_API_KEY" } });
  fireEvent.click(button(secrets(), "Add"));
  expect(
    await within(secrets()).findByText("the secret OPENAI_API_KEY is empty; to remove it: lado project unset shop OPENAI_API_KEY"),
  ).toBeTruthy();
});

test("Replace opens an empty hidden field and closes it emptied", async () => {
  open();
  fireEvent.click(button(row(secrets(), "GH_TOKEN"), "Replace"));
  const field = secretField();
  expect(field.getAttribute("placeholder")).toBe("New value (the old one is not shown)");
  expect(field.getAttribute("aria-label")).toBe("New value of GH_TOKEN");
  expect(field.value).toBe("");
  expect((button(secrets(), "Replace") as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(field, { target: { value: "canary-replace" } });
  expect((button(secrets(), "Replace") as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(button(secrets(), "Replace"));
  await waitFor(() => expect(secrets().querySelector("input[type=password]")).toBeNull());
  expect(field.value).toBe("");
  expect(server.calls("PUT", "/api/projects/shop/secrets/GH_TOKEN")[0].body).toEqual({ value: "canary-replace" });
});

test("the value field is emptied when the page goes away", () => {
  const { unmount } = open();
  fireEvent.click(button(row(secrets(), "GH_TOKEN"), "Replace"));
  const field = secretField();
  fireEvent.change(field, { target: { value: "canary-leave" } });
  unmount();
  expect(field.value).toBe("");
});

test("removing a secret asks in its row", async () => {
  open();
  fireEvent.click(button(row(secrets(), "GH_TOKEN"), "Remove"));
  expect(secrets().textContent).toContain("Remove GH_TOKEN?");
  fireEvent.click(button(secrets(), "Cancel"));
  expect(server.asked).toEqual([]);
  fireEvent.click(button(row(secrets(), "GH_TOKEN"), "Remove"));
  fireEvent.click(button(secrets(), "Remove"));
  await waitFor(() => expect(within(secrets()).queryByText("GH_TOKEN")).toBeNull());
});

// The marks

test("a name the outside folder gives too is marked, with its tooltip", () => {
  open(
    project("shop", {
      variables: [{ name: "BOARD_URL", value: "x" }],
      secrets: ["YOUGILE_API_KEY"],
      overrides: ["BOARD_URL", "YOUGILE_API_KEY"],
    }),
  );
  const mark = within(row(secrets(), "YOUGILE_API_KEY")).getByText("overrides outside value");
  expect(mark.getAttribute("title")).toBe(
    "The outside folder (LADO_ENV_DIR) also gives YOUGILE_API_KEY. This project's sessions get the " +
      "project's value; its outside value is not shown.",
  );
  expect(within(row(variables(), "BOARD_URL")).getByText("overrides outside value")).toBeTruthy();
});

test("a secret file the agents do not get is named in its row, others under the block", () => {
  open(
    project("shop", {
      secrets: ["SENTRY_DSN"],
      unused: [
        { name: "SENTRY_DSN", reason: "readable or writable by others: chmod 600 it" },
        { name: "LINKED", reason: "a symbolic link" },
        { name: null, reason: "readable or writable by others: chmod 700 it" },
      ],
    }),
  );
  const sentry = row(secrets(), "SENTRY_DSN");
  expect(sentry.textContent).toContain("⚠ Agents do not get it: readable or writable by others: chmod 600 it");
  expect(within(sentry).getByRole("button", { name: "Replace" })).toBeTruthy();
  expect(sentry.textContent).not.toContain("set · hidden");
  expect(secrets().textContent).toContain("⚠ LINKED: agents do not get it: a symbolic link");
  expect(secrets().textContent).toContain(
    "⚠ The secrets folder is not used: readable or writable by others: chmod 700 it",
  );
});
