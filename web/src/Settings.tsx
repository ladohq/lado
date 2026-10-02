// Settings: one page, its sections one under the other; a new one goes at the end.
import { useId, useState } from "react";

import { PLANS } from "./paths";
import { Placeholder } from "./Placeholder";
import { chooseTheme, storedTheme, type Theme } from "./prefs";
import { useTitle } from "./Shell";

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
      <Placeholder title="Providers and environment" plan={PLANS.providers}>
        The agent CLIs LADO can run, their versions and logins, and what <code>lado doctor</code> checks.
      </Placeholder>
    </div>
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
