import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { TelemetryInfo } from "./api";
import { sentWhen, StatisticsQuestion, StatisticsSetting, statisticsLine } from "./Telemetry";

function telemetry(more: Partial<TelemetryInfo> = {}): TelemetryInfo {
  return {
    choice: null,
    on: false,
    ask: true,
    off_by: null,
    endpoint: true,
    last_sent: null,
    last_error: null,
    waiting: 0,
    new_fields: [],
    ...more,
  };
}

const PREVIEW = {
  report: { event: "lado_daily", properties: { lado: "0.37.0", sessions: 3 } },
  errors: [{ event: "$exception", properties: { type: "KeyError" } }],
};

let state: TelemetryInfo;

function serve() {
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (path === "/api/telemetry" && init?.method === "POST") {
      const { choice } = JSON.parse(String(init.body)) as { choice: "on" | "off" };
      state = telemetry({ choice, on: choice === "on", ask: false });
      return json(state);
    }
    if (path === "/api/telemetry") return json(state);
    if (path === "/api/telemetry/preview") return json(PREVIEW);
    return json([]);
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

beforeEach(() => {
  state = telemetry();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("the banner shows while ask is true and goes after Send statistics", async () => {
  const fetch = serve();
  render(<StatisticsQuestion ready />);
  const banner = await screen.findByRole("region", { name: "Usage statistics" });
  expect(banner.textContent).toContain("Help improve LADO?");
  expect(banner.textContent).toContain("Nothing is sent until you choose.");
  fireEvent.click(screen.getByRole("button", { name: "Send statistics" }));
  await waitFor(() => expect(screen.queryByRole("region", { name: "Usage statistics" })).toBeNull());
  expect(fetch).toHaveBeenCalledWith(
    "/api/telemetry",
    expect.objectContaining({ method: "POST", body: JSON.stringify({ choice: "on" }) }),
  );
});

test("Don't send posts off", async () => {
  const fetch = serve();
  render(<StatisticsQuestion ready />);
  fireEvent.click(await screen.findByRole("button", { name: "Don't send" }));
  await waitFor(() => expect(screen.queryByRole("region", { name: "Usage statistics" })).toBeNull());
  expect(fetch).toHaveBeenCalledWith("/api/telemetry", expect.objectContaining({ body: JSON.stringify({ choice: "off" }) }));
});

test("What is sent loads the preview once", async () => {
  const fetch = serve();
  render(<StatisticsQuestion ready />);
  const summary = await screen.findByText("What is sent");
  const details = summary.parentElement as HTMLDetailsElement;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  expect(await screen.findByText(/"lado_daily"/)).toBeTruthy();
  details.open = false;
  fireEvent(details, new Event("toggle"));
  details.open = true;
  fireEvent(details, new Event("toggle"));
  const previews = fetch.mock.calls.filter(([path]) => path === "/api/telemetry/preview");
  expect(previews).toHaveLength(1);
});

test("the banner names the fields a stored yes does not cover", async () => {
  state = telemetry({ new_fields: ["models"] });
  serve();
  render(<StatisticsQuestion ready />);
  expect(await screen.findByText("LADO now also sends: models.")).toBeTruthy();
});

test("the banner asks nothing of the server before the event stream is open", () => {
  const fetch = serve();
  render(<StatisticsQuestion ready={false} />);
  expect(fetch).not.toHaveBeenCalled();
});

test("no banner when ask is false", async () => {
  state = telemetry({ ask: false, choice: "off" });
  const fetch = serve();
  render(<StatisticsQuestion ready />);
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByRole("region", { name: "Usage statistics" })).toBeNull();
});

test("Settings shows Send checked and the last-sent line", async () => {
  const sent = new Date();
  sent.setHours(9, 12);
  state = telemetry({ choice: "on", on: true, ask: false, last_sent: sent.toISOString() });
  serve();
  render(<StatisticsSetting />);
  const send = await screen.findByRole("radio", { name: "Send" });
  await waitFor(() => expect((send as HTMLInputElement).checked).toBe(true));
  expect(screen.getByText(/Last sent today at 09:12/)).toBeTruthy();
  expect(screen.getByText("What the next report sends")).toBeTruthy();
});

test("Settings: not chosen yet", async () => {
  serve();
  render(<StatisticsSetting />);
  expect(await screen.findByText(/Not chosen yet: nothing is sent\./)).toBeTruthy();
  expect(screen.getByRole("heading").textContent).toBe("Usage statistics — not chosen yet");
  const radios = screen.getAllByRole("radio") as HTMLInputElement[];
  expect(radios.map((radio) => radio.checked)).toEqual([false, false]);
  fireEvent.click(screen.getByRole("radio", { name: "Don't send" }));
  await waitFor(() => expect((screen.getByRole("radio", { name: "Don't send" }) as HTMLInputElement).checked).toBe(true));
});

test("Settings: disabled with the variable when off_by", async () => {
  state = telemetry({ choice: "on", ask: false, off_by: "DO_NOT_TRACK=1" });
  serve();
  render(<StatisticsSetting />);
  expect(await screen.findByText("DO_NOT_TRACK=1")).toBeTruthy();
  expect(screen.getByText(/is set in the LADO server's environment\./)).toBeTruthy();
  const off = screen.getByRole("radio", { name: "Don't send" }) as HTMLInputElement;
  expect(off.checked).toBe(true);
  expect(off.matches(":disabled")).toBe(true); // its fieldset is
  expect(screen.getByRole("heading").textContent).toBe("Usage statistics — switched off by the environment");
});

test("the panel's row texts", () => {
  const now = new Date();
  const today = new Date(now);
  today.setHours(9, 12);
  expect(statisticsLine(telemetry({ choice: "on", on: true, last_sent: today.toISOString() }), now)).toBe(
    "sending · last today 09:12",
  );
  expect(statisticsLine(telemetry({ choice: "on", on: true }), now)).toBe("sending · not sent yet");
  expect(statisticsLine(telemetry({ choice: "off" }))).toBe("off");
  expect(statisticsLine(telemetry())).toBe("not chosen");
  expect(statisticsLine(telemetry({ choice: "on", off_by: "LADO_TELEMETRY=0" }))).toBe("off: LADO_TELEMETRY=0");
  expect(statisticsLine(telemetry({ endpoint: false }))).toBe("off: no endpoint");
});

test("the last send's day", () => {
  const now = new Date(2026, 9, 13, 18, 0);
  expect(sentWhen(new Date(2026, 9, 12, 9, 12).toISOString(), now)).toBe("yesterday 09:12");
});
