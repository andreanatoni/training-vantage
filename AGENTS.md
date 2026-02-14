# Repository Guidelines

## Project Structure & Module Organization
Training Vantage is a CLI-first repository rooted at `./tv` (bash dispatcher). Core command logic lives in `scripts/` (Python), persistent state in `data/*.json`, canonical nutrition/running knowledge in `knowledge/`, source material in `sources/`, and generated nutrition plans in `plans/nutrition/`.

Key paths:
- `tv`: command entrypoint (`./tv status`, `./tv plan --all`)
- `scripts/`: implementation of `status`, `weigh`, `zones`, `plan`, `week`
- `data/`: runtime records (`composition.json`, `zones.json`, `running-log.json`, `changelog.json`)
- `plans/nutrition/`: generated markdown plans by category

## Build, Test, and Development Commands
No build step is required; run commands directly.

- `./tv help`: list available commands
- `./tv status`: print current athlete/program dashboard
- `./tv weigh 68.5 13.0 "note"`: append body-composition measurement
- `./tv zones 18:15 "post race"`: recalculate running zones from 5K test
- `./tv plan forza` or `./tv plan --all`: generate one/all nutrition plans
- `./tv week 20`: inspect a weekly running plan

## Coding Style & Naming Conventions
Use Python 3 with PEP 8 conventions:
- 4-space indentation, `snake_case` for functions/variables, `UPPER_SNAKE_CASE` for constants
- keep scripts small and command-focused; favor pure helper functions
- preserve existing JSON schema and field names when writing to `data/`

For shell (`tv`), keep command dispatch explicit via `case` arms.

## Testing Guidelines
There is no automated test suite yet. Validate changes with targeted CLI runs against realistic data:
- smoke test command behavior via `./tv help`, `./tv status`, `./tv week 1`
- for write operations (`weigh`, `zones`, `plan`), verify expected diffs in `data/` and `plans/nutrition/`
- avoid manual schema drift in JSON files

## Commit & Pull Request Guidelines
Current history is minimal (`Initial commit: Training Vantage CLI v1.0`). Keep future commits clear and scoped:
- subject format: `<area>: <imperative summary>` (example: `zones: validate 5k time parsing`)
- one logical change per commit; include data/file regeneration in same commit when required

PRs should include:
- purpose and behavioral impact
- commands run for verification
- sample output snippets or changed file references (especially `data/*.json` and `plans/nutrition/*.md`)

## Data & Configuration Safety
Treat `knowledge/` as source-of-truth content. Do not edit it casually. Any change affecting generated plans or tracked metrics should be traceable in `data/changelog.json`.
