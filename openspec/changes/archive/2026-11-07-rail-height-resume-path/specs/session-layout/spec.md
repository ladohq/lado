## ADDED Requirements

### Requirement: In a wide window the rail is as high as the app

In a window wider than 900 px the rail SHALL be as high as the app, on every page, so that on a
touch screen, where the app is as high as the part of the window the human sees, Report a bug
and Settings stand within that part. A wider window with a fine pointer SHALL keep a rail as
high as the window.

#### Scenario: A tablet held sideways
- **WHEN** the UI is opened on a touch screen 1180 px wide and 688 px high, and the part of the
  window the human sees is 560 px high
- **THEN** the rail is 560 px high and Settings ends within those 560 px

#### Scenario: A computer's window
- **WHEN** the UI is opened with a mouse in a window 1280 px wide and 800 px high
- **THEN** the rail is 800 px high

#### Scenario: A tablet held upright
- **WHEN** a session's page is opened on a touch screen 820 px wide, and the part of the window
  the human sees is 600 px high
- **THEN** the rail is 600 px high, as it was
