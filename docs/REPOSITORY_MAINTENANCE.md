# Repository maintenance

Audit date: 2026-10-28. This records observed state and separates proposed settings
from applied changes. Published releases, version tags, application identifiers,
updater keys, data paths and user workspaces are preserved.

## Integration baseline

After fetching origin, `main` was `26add3e`, with one unique merge commit and
fourteen commits on `release/0.1.10` (`e61ae25`). The newest published preview is
`v0.1.10-rc.2`, exactly `5a18d8c4caf5eb6d0c1cf45e4e90792218090fee`;
its desktop preview workflow run `40693994035` succeeded. Release metadata says
`target_commitish: main`; that field is not the tag's actual commit.

`chore/sync-main-0.1.10` starts at the current release branch and merges
`origin/main` with a merge commit. Both histories remain reachable. The merge
has no tree changes relative to `e61ae25`; no newer implementation is replaced.
Keep a merge commit for this synchronization PR so ancestry remains useful.
Routine subsequent PRs can use squash merges.

PR #5's head (`f0f0862`) is an ancestor of the integration baseline. PR #4's
commit (`7334c36`) is not an ancestor, but its nine engineering contract files
were adopted by `676f835`. Contracts match except deliberate architecture
version/signing corrections; the README was expanded in #5. Close these drafts
as superseded only after synchronization reaches main. No branch is deleted.

## Confirmed GitHub state before changes

- Public repository; default branch `main`, unprotected; rulesets API returned `[]`.
- PRs #1–3 merged; #4 and #5 open drafts.
- Issues enabled; discussions disabled; automatic branch deletion and auto-merge disabled.
- Squash, merge and rebase merging enabled. Existing metadata points to the README.
- Six workflows on the release branch. Ordinary CI repeats sidecar packaging and
  Rust checks; desktop PR builds repeat deterministic checks across three OSes.
- Model acceptance downloads models for every backend PR. The existing preview
  publication waits for all desktop targets, PDF smoke and model acceptance.
- Release publication/signing and license inventories already exist; preserve them.
- No Dependabot, security policy, ESLint or Ruff enforcement at audit start.
- Working tree was clean. GitHub CLI is absent. The connected GitHub tools support
  PR creation/merging and read APIs, but no repository administration mutations.
  An API permissions response reporting admin access does not supply a usable
  administration tool. Settings below must be applied with an administrator's CLI.

## Administrator handoff

The proposed policy follows GitHub's [ruleset documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets).
The `verify` source is GitHub Actions (app ID 15368), observed on the tooling PR.
No administrator settings have been applied through the connected tools.

Run only after the synchronization and tooling PRs have green checks on main.
Inspect the actual check-run name before activating required checks:

```bash
gh api repos/artemkolokoltsev/colloquily/commits/main/check-runs --jq '.check_runs[].name'
gh api --method PATCH repos/artemkolokoltsev/colloquily \
  -f description='Local-first, open-source AI study companion for university oral exams. Source-grounded practice, private on-device inference, and desktop support.' \
  -f homepage='https://colloquily.com' -F delete_branch_on_merge=true \
  -F allow_squash_merge=true -F allow_merge_commit=true -F allow_rebase_merge=false
gh api --method PUT repos/artemkolokoltsev/colloquily/topics \
  --input .github/repository-topics.json
gh api --method POST repos/artemkolokoltsev/colloquily/rulesets \
  --input .github/protect-main.json
gh api --method PUT repos/artemkolokoltsev/colloquily/vulnerability-alerts
gh api --method PUT repos/artemkolokoltsev/colloquily/private-vulnerability-reporting
```

Keep merge commits available for history reconciliation. Do not create duplicate
rulesets: inspect existing rulesets first and PATCH the returned ID if already
present. Required checks must be confirmed successful before activation, with no
path filter on the deterministic workflow. The proposed ruleset requires zero
approvals, resolved conversations, PRs, and CI; blocks deletion/force pushes;
and has no bypass actors. Auto-merge is optional and remains disabled until this
policy is working. Keep issues enabled and discussions disabled unless there is
a concrete moderation/use case.

## Release and branch lifecycle

Synchronization PR #6 merged as `5beee1c` after local deterministic verification
and hosted verify, Chromium/WebKit, all three native packaging targets and
synthetic real-model acceptance passed. Main now contains the latest released
implementation and both histories. Subsequent tooling/governance/reliability
changes are separated into PRs #7, #8 and #9 (consult GitHub for merge status).

Use short-lived `feat/`, `fix/`, `docs/`, `refactor/`, `chore/` branches, reviewed
PRs into main, then immutable version tags on the intended integrated commit.
Housekeeping does not bump versions. Existing `latest` is a legacy moving download
channel reference, not an immutable version tag; preserve it and the download
publication mechanism. Do not convert existing tags or recreate releases.

Branch retirement requires explicit approval. After synchronization is merged,
recheck reachability with `git merge-base --is-ancestor origin/BRANCH origin/main`.
Use the branch inventory below as evidence, not deletion authorization. Preserve
branches with unique work; a release tag can preserve history but does not prove
that its changes are integrated into main.

## Verification limitations

Initial dependency installation and Python tests failed because the host disk was
full (ENOSPC); those runs are not test passes. Regenerable compiler/build caches
were removed with explicit command approval. Subsequent results belong in the PR
and final delivery record. Native installation, OS publisher trust and model
quality need their own validation; deterministic checks do not establish them.

## Branch inventory before synchronization

| Branch | Head | In integration baseline | Version tag preserving head | Associated PR/release | Action after merge |
| --- | --- | --- | --- | --- | --- |
| `cleanup-desktop` | `d42fd3d` | yes | — | #1 (merged) | Review explicit retirement approval |
| `docs/engineering-contracts-2026-10` | `7334c36` | no | — | #4 (closed as superseded) | Preserve; unique ancestry (PR #4 content adopted) |
| `docs/ui-practice-engineering` | `f0f0862` | yes | — | #5 (closed as integrated) | Review explicit retirement approval |
| `fix/windows-sqlite-handles` | `c745acc` | yes | — | #2 (merged) | Review explicit retirement approval |
| `main` | `26add3e` | yes | latest, v0.1.1-rc.1 | Default branch | Keep permanently |
| `release-v0.1.0` | `c809f0f` | no | — | Historical branch; no matching head tag | Preserve; inspect unique work |
| `release/0.1.1-readiness` | `a791863` | yes | — | #3 (merged) | Review explicit retirement approval |
| `release/0.1.10` | `e61ae25` | yes | — | v0.1.10-rc.2 (ancestor of head) | Review explicit retirement approval |
| `release/0.1.2` | `1d3c7b5` | yes | v0.1.2-rc.1 | v0.1.2-rc.1 | Review explicit retirement approval |
| `release/0.1.3` | `93aa7c4` | yes | v0.1.3-rc.1 | v0.1.3-rc.1 | Review explicit retirement approval |
| `release/0.1.4` | `24fab98` | yes | v0.1.4-rc.1 | v0.1.4-rc.1 | Review explicit retirement approval |
| `release/0.1.5` | `060d6b9` | yes | v0.1.5-rc.1 | v0.1.5-rc.1 | Review explicit retirement approval |
| `release/0.1.6` | `392241b` | yes | v0.1.6-rc.1 | v0.1.6-rc.1 | Review explicit retirement approval |
| `release/0.1.7` | `722f07a` | yes | v0.1.7-rc.1 | v0.1.7-rc.1 | Review explicit retirement approval |
| `release/0.1.8` | `336296d` | yes | v0.1.8-rc.1 | v0.1.8-rc.1 | Review explicit retirement approval |
| `release/0.1.9` | `c04562a` | yes | v0.1.9-rc.1 | v0.1.9-rc.1 | Review explicit retirement approval |

## Post-synchronization retirement assessment

Rechecked against fetched main `5beee1c`: thirteen original non-main branch heads
are reachable and are retirement candidates requiring explicit approval (all rows
marked “yes” except main). `docs/engineering-contracts-2026-10` has one unique
commit, and `release-v0.1.0` has eleven unique commits with no containing version
tag. Preserve both; adopted/squashed content is not sufficient deletion evidence.
PRs #4/#5 were closed only after content/ancestry checks against synchronized main.
No original remote branch has been deleted. The four maintenance branches are
new deliverable branches; assess them separately after their PRs merge.

## Delivery verification

| Scope | Evidence |
| --- | --- |
| Local deterministic | `make check` on Python 3.11 / Node 22.14 passed: 70 domain, 126 API, 17 frontend and 4 tooling tests; lint/format ratchets, strict TypeScript, version/translation parity and build |
| Local Rust | `make desktop-check` passed: rustfmt, Clippy with warnings denied, locked compilation |
| Local browsers | Chromium and WebKit production-CSP suite passed, including stale exam response, duplicate submission and keyboard/focus regressions |
| Report extraction | Five characterization tests passed before and after extraction; historical import names preserved |
| Synchronization hosted CI | PR #6: verify, PDF readers, all three native packaging targets and real-model synthetic-learning passed before merge |
| Tooling hosted CI | PR #7 final head `abc7ad9`: deterministic aggregate, PDF smoke, Intel native runtime and repeated real-model acceptance all passed. The initial ARM capacity failure occurred before any steps ran. Merged as `124b145` |
| Governance hosted CI | PR #8 deterministic aggregate passed; merged as `0e0699e` |
| Reliability hosted CI | PR #9 head `5071f1e`: deterministic aggregate, Chromium/WebKit and native runtime all passed; the final documentation-only update retains this implementation |
| Not performed | Clean-machine GUI installation, current OS publisher-signing approval, full fresh Python/Cargo advisory audit |

The frontend bundle retains Vite's existing >500 kB chunk warning. Python still
has bounded requirements rather than a full resolved lock. Legacy diagnostic
fingerprints remain (106 at rollout); formatting debt drops from 111 to 110 files
with the practice extraction. Broad Python typing and React component tooling
were evaluated and deferred: strict TypeScript and existing real-browser tests
provide the immediate gate without introducing a duplicate interaction stack.

Priorities after this delivery: activate/recheck administrator settings; review
branch retirement approval; maintain and reduce the quality baseline; add a
reproducible Python dependency lock with native/license validation; collect
clean-machine installation evidence. Additional async failure scenarios can
extend the reusable browser helpers; avoid rewriting the domain layers.

## Maintenance file manifest

The following paths changed relative to release baseline `e61ae25`. The larger
release-to-main source integration is separately reviewable in PR #6's Files
changed view; it is not an application rewrite in the maintenance PRs.

- `.github/ISSUE_TEMPLATE/bug.yml`
- `.github/ISSUE_TEMPLATE/feature.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/dependabot.yml`
- `.github/protect-main.json`
- `.github/repository-topics.json`
- `.github/workflows/ci.yml`
- `.github/workflows/desktop-validation.yml`
- `.github/workflows/desktop.yml`
- `.github/workflows/download-channel.yml`
- `.github/workflows/learning-quality.yml`
- `.github/workflows/pdf-reader.yml`
- `.github/workflows/release.yml`
- `.prettierignore`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `Makefile`
- `README.md`
- `SECURITY.md`
- `backend/core/services/exam_state.py`
- `backend/core/services/practice_report.py`
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT.md`
- `docs/ENGINEERING_BASELINE.md`
- `docs/ENGINEERING_CASE_STUDIES.md`
- `docs/ENGINEERING_STANDARDS.md`
- `docs/REPOSITORY_MAINTENANCE.md`
- `docs/adr/0002-pure-practice-report.md`
- `docs/security-review.md`
- `eslint.config.mjs`
- `package-lock.json`
- `package.json`
- `pyproject.toml`
- `requirements-dev.txt`
- `rust-toolchain.toml`
- `scripts/check_quality.py`
- `scripts/quality-baseline.json`
- `scripts/smoke_pdf_reader.mjs`
- `src-tauri/build.rs`
- `src-tauri/src/main.rs`
- `tests/core/test_practice_report.py`
- `tests/frontend/browserReliability.mjs`
- `tests/tooling/test_quality.py`
