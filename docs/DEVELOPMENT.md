# Developer verification

Use Python 3.11, Node 22.13+ on the 22 LTS line (or Node 24+), and `npm ci`.
Activate a virtual environment, then `python -m pip install -r requirements-dev.txt`.
The Node engine range excludes Node 23, which upstream ESLint does not support.

| Command | Scope |
| --- | --- |
| `make test` | Version/translations, frontend utilities, tooling, API and domain tests |
| `make lint` | Ruff and ESLint (including both React hooks rules) ratchet |
| `make format-check` | Ruff format and Prettier ratchet |
| `make typecheck` | Strict TypeScript without emitting bundles |
| `make check` | All the above and production frontend build; no model downloads or signing |
| `make desktop-check` | Rust format, strict Clippy and locked compilation |
| `npm run test:pdf` | Synthetic Chromium/WebKit production-CSP interaction checks |

On Windows use the package scripts and Python commands in the Makefile if Make
is unavailable. Desktop checks require platform prerequisites, generated sidecar
and icons; build the sidecar first. Native installers and real-model acceptance
remain separate from deterministic checks.

## Incremental formatting and lint policy

The measured baseline contains 106 diagnostic fingerprints and 111 unformatted
files. `scripts/quality-baseline.json` records existing debt, not exemptions for
all future edits to those files. Lint fingerprints include file, rule, message,
source line and multiplicity; moving a line does not create a violation, but a
new or duplicated violation does. Syntax/parser errors cannot be baselined.
Formatting exceptions match UTF-8 file contents after normalizing line endings
for Windows compatibility. Editing an unformatted legacy
file requires formatting that file. New files must pass outright. Removed/fixed
entries are allowed; remove their stale baseline entries during maintenance.

Use `python -m ruff format path.py` and `npx prettier --write path.tsx` for files
you change. Do not run a whole-repository format alongside functional edits.
`python scripts/check_quality.py MODE --write-baseline` is reserved for explicit,
reviewed tool migrations. Never regenerate the baseline to make a failing PR
green. Tool failure is fatal. The fingerprint approach can miss a replacement
with identical text/rule/message; review remains necessary.

Python checks focus on runtime mistakes (Ruff E4/E7/E9/F). Broad Python typing is
deferred until legacy import aliases and domain contracts have a measured scope;
strict frontend typing is enforced now. Rust formatting is normalized in the
tooling change, and Clippy currently passes with warnings denied.

## CI responsibilities

`ci.yml` runs Python and frontend checks independently, with an always-running
`verify` aggregate. Only this unconditional aggregate is suitable as a required
check. `desktop-validation.yml` selectively packages/smokes the runtime and
checks Rust for runtime/build changes; dispatch it for other desktop risks.
Selective runtime validation uses macOS Intel after hosted ARM runner-capacity
failures during rollout; this does not replace architecture coverage in release
builds. `desktop.yml` preserves the three-target preview builds for tags and dispatch,
and no longer builds all installers on every frontend PR. PDF browser smoke
retains its selective PR trigger. Model acceptance runs on model/evidence paths,
explicit dispatch, and release candidates; it is not a required routine check.

Publication still waits for complete multi-platform artifacts and acceptance.
Updater signatures, OS publisher signing, license inventories and permanent
download channels retain their existing implementation. Action SHAs were resolved
from upstream tags; dependency automation should maintain them.

## Troubleshooting

ENOSPC failures require free disk space before repeating installs/tests. Never
delete study data or SQLite files to recover space. A failed dependency install
can leave `node_modules` incomplete; retry `npm ci` after recovering space.
Do not claim native installation from a compile check, or model quality from
synthetic HTTP fixtures. See [maintenance](REPOSITORY_MAINTENANCE.md) for repository
settings and [desktop packaging](desktop.md) for heavy checks.
