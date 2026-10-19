## ADDED Requirements

### Requirement: A chip's type follows the server's limits once they load

An attached file's chip (in the composer and in the waiting card's answer fields) SHALL
show its thumbnail or type icon and the crossed-out eye by the media type the server's
limits (`GET /api/limits`) give its name at the time the chip is shown, never by a type
fixed when the file was attached: a file attached before the limits load SHALL show the
generic icon and no eye until they load, and then exactly as a file attached after they
loaded.

#### Scenario: Files attached before the limits load

- **WHEN** the human attaches `screenshot.png`, `server.log` and `spec.pdf` before the
  composer's limits have loaded, and the limits then load
- **THEN** `screenshot.png` shows its thumbnail, `server.log` its text icon, and only
  `spec.pdf` has the crossed-out eye

#### Scenario: Files attached after the limits load

- **WHEN** the human attaches the same three files after the limits have loaded
- **THEN** the chips are the same as in the scenario "Files attached before the limits
  load"

#### Scenario: Before the limits load

- **WHEN** files are attached and the limits have not loaded yet
- **THEN** each chip shows the generic file icon, its name and size, and no crossed-out eye
