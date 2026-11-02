## ADDED Requirements

### Requirement: lado project set refuses its command line without repeating it

When argparse refuses the command line of `lado project set`, the command SHALL print
its usage and one fixed text on stderr, exit 1, reading nothing from stdin and storing
nothing; no word of the command line SHALL appear in its output, on Python 3.10 and later
alike. `-h` or `--help` alone SHALL print the help, exit 0.

#### Scenario: The fixed text
- **WHEN** argparse refuses the command line of `lado project set` (a word it does not
  take, a value starting with `-` before `--`, an argument given to `--secret`, `-h` or
  `--help`, a missing id or name)
- **THEN** stderr holds the usage and then `lado: lado project set takes <id> <NAME>, a
  value and --secret, nothing more; a value starting with - goes after -- (lado project
  set <id> <NAME> -- -v); a secret's value is never given on the command line (ps and the
  shell's history keep it): run lado project set <id> <NAME> --secret and type it, or pipe
  it in`, stdout is empty, and the exit status is 1

#### Scenario: A dashed secret before --secret
- **WHEN** the human runs `lado project set shop GH_TOKEN -s3cr3t --secret`
- **THEN** it prints the usage and the fixed text on stderr, exits 1, `-s3cr3t` is in
  neither stdout nor stderr, and `shop` keeps its secrets as they were

#### Scenario: A dashed secret after --secret, or after a prefix of it
- **WHEN** the human runs `lado project set shop GH_TOKEN --secret -s3cr3t` or `lado
  project set shop GH_TOKEN --s -s3cr3t`
- **THEN** it exits 1 with the usage and the fixed text, and `-s3cr3t` is not printed

#### Scenario: An argument given to a flag
- **WHEN** the human runs `lado project set shop GH_TOKEN` with `--secret=s3cr3t`,
  `--help=s3cr3t`, `--he=s3cr3t`, `-h=s3cr3t` or `-hs3cr3t`
- **THEN** it exits 1 with the usage and the fixed text, and `s3cr3t` is not printed

#### Scenario: A second word
- **WHEN** the human runs `lado project set shop GH_TOKEN ghp a1 --secret`
- **THEN** it exits 1 with the usage and the fixed text, and neither `ghp` nor `a1` is
  printed

#### Scenario: A plain variable's dashed value without --
- **WHEN** the human runs `lado project set shop FLAGS -v`
- **THEN** it exits 1 with the usage and the fixed text, and `shop` has no variable
  `FLAGS`; `lado project set shop FLAGS -- -v` sets it as before

#### Scenario: Help alone
- **WHEN** the human runs `lado project set --help`
- **THEN** it prints the command's help and exits 0
