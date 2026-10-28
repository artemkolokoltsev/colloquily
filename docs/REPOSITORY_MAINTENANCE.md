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

| Branch | Head | In integration baseline | Version tag preserving head | Action after merge |
| --- | --- | --- | --- | --- |
| `cleanup-desktop` | `d42fd3d` | yes | — | Review explicit retirement approval |
| `docs/engineering-contracts-2026-10` | `7334c36` | no | — | Preserve; unique ancestry (PR #4 content adopted) |
| `docs/ui-practice-engineering` | `f0f0862` | yes | — | Review explicit retirement approval |
| `fix/windows-sqlite-handles` | `c745acc` | yes | — | Review explicit retirement approval |
| `main` | `26add3e` | yes | latest, v0.1.1-rc.1 | Keep permanently |
| `release-v0.1.0` | `c809f0f` | no | — | Preserve; inspect unique work |
| `release/0.1.1-readiness` | `a791863` | yes | — | Review explicit retirement approval |
| `release/0.1.10` | `e61ae25` | yes | — | Review explicit retirement approval |
| `release/0.1.2` | `1d3c7b5` | yes | v0.1.2-rc.1 | Review explicit retirement approval |
| `release/0.1.3` | `93aa7c4` | yes | v0.1.3-rc.1 | Review explicit retirement approval |
| `release/0.1.4` | `24fab98` | yes | v0.1.4-rc.1 | Review explicit retirement approval |
| `release/0.1.5` | `060d6b9` | yes | v0.1.5-rc.1 | Review explicit retirement approval |
| `release/0.1.6` | `392241b` | yes | v0.1.6-rc.1 | Review explicit retirement approval |
| `release/0.1.7` | `722f07a` | yes | v0.1.7-rc.1 | Review explicit retirement approval |
| `release/0.1.8` | `336296d` | yes | v0.1.8-rc.1 | Review explicit retirement approval |
| `release/0.1.9` | `c04562a` | yes | v0.1.9-rc.1 | Review explicit retirement approval |
