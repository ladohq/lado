// Settings → General (docs/design/ui.md, General): the theme and browser notifications.
import { useState } from "react";

import { NotificationsSetting } from "./Notifications";
import { chooseTheme, storedTheme, type Theme } from "./prefs";
import { SettingsPage } from "./SettingsPage";

const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export function GeneralPage() {
  const [theme, setTheme] = useState(storedTheme);
  const choose = (value: Theme) => {
    setTheme(value);
    chooseTheme(value);
  };
  return (
    <SettingsPage slug="general">
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
      <NotificationsSetting />
    </SettingsPage>
  );
}
