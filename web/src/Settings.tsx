// Settings: one page, its sections one under the other; a new one goes at the end.
import { useId, useState } from "react";

import { NotificationsSetting } from "./Notifications";
import { chooseTheme, storedTheme, type Theme } from "./prefs";
import { Providers } from "./Providers";
import { useTitle } from "./Shell";
import { StatisticsSetting } from "./Telemetry";

const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export function Settings() {
  useTitle("Settings");
  return (
    <div className="settings">
      <Appearance />
      <Notifications />
      <Providers />
      <StatisticsSetting />
    </div>
  );
}

function Notifications() {
  const id = useId();
  return (
    <section className="setting" aria-labelledby={id}>
      <h2 id={id}>Notifications</h2>
      <NotificationsSetting />
    </section>
  );
}

function Appearance() {
  const id = useId();
  const [theme, setTheme] = useState(storedTheme);
  const choose = (value: Theme) => {
    setTheme(value);
    chooseTheme(value);
  };
  return (
    <section className="setting" aria-labelledby={id}>
      <h2 id={id}>Appearance</h2>
      <fieldset className="choice">
        <legend>Theme</legend>
        <div className="segments">
          {THEMES.map((option) => (
            <label key={option.value}>
              <input
                type="radio"
                name="theme"
                value={option.value}
                checked={theme === option.value}
                onChange={() => choose(option.value)}
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      <p className="muted">System follows your computer's light or dark setting.</p>
    </section>
  );
}
