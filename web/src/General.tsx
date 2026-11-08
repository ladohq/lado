// Settings → General (docs/design/ui.md, General): two setting rows, the theme and browser
// notifications (Notifications.tsx); a row's name labels its control.
import { useId, useState } from "react";

import { NotificationsSetting } from "./Notifications";
import { chooseTheme, storedTheme, type Theme } from "./prefs";
import { SettingsPage } from "./SettingsPage";

const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export function GeneralPage() {
  const id = useId();
  const [theme, setTheme] = useState(storedTheme);
  const choose = (value: Theme) => {
    setTheme(value);
    chooseTheme(value);
  };
  return (
    <SettingsPage slug="general">
      <div className="srows">
        <div className="srow" id="theme">
          <div className="srow-text">
            <span className="srow-name" id={id}>
              Theme
            </span>
          </div>
          <div className="srow-ctl">
            <fieldset className="choice" aria-labelledby={id}>
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
          </div>
        </div>
        <NotificationsSetting />
      </div>
    </SettingsPage>
  );
}
