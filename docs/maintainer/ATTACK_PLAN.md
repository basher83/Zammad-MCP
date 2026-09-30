# Attack plan: clear the open PR board

**Written 2026-09-29 against `main` = `0d02c45`.** This replaces the ledger's
"triage attention order" with an execution plan. It was built by fetching every open
PR head, merging candidates onto a scratch branch in sequence, and running the full
local gate (`ruff format --check`, `ruff check`, `mypy`, `pytest`) after each merge.
Results are recorded below; nothing here is inferred from titles or bot comments.

## Verdict on the existing triage

The ledger (PR_LEDGER.md, STATUS.md, DEPENDENCIES.md) is accurate as a record and its
family groupings and commit-ancestry claims all checked out against git. Its weakness
is that it is written as a governance document: every family ends in "record a
decision", "delta-review", or "communicate disposition", and it never asks whether
the code actually merges and passes. Three things it gets wrong or overweights:

1. **It treats each PR as a unit to be reviewed and merged on its own.** That is the
   slowest possible path. 38 of 41 PRs branch from the same base commit `8873b2e`
   and edit the same three files (`client.py`, `models.py`, `server.py`). Merged
   one at a time through GitHub, every merge re-conflicts every remaining PR.
   Merged in one integration branch, the conflicts are 2 to 9 hunks each and
   resolve in minutes.
2. **It defers to stale CI signals.** The `security-scan` failure on every factory PR
   is a `pip-audit` finding that `main` fixed in `38e1678`; the scan is green on
   `main` as of 2026-09-28. Fork PRs never ran tests at all (3 checks, all
   bots). Neither says anything about the code. Locally, `main` is fully green:
   222 tests, lint and mypy clean.
3. **It keeps alternatives alive.** Six PRs are duplicates or supersets of others and
   should simply be closed once their carrier lands. Merge commits keep the original
   author on their commits, so credit is preserved without merging the duplicate.

## What the merge train showed

Sequential merges onto `main`, in this order, with the full gate after each:

| Step | PR | Result |
| --- | --- | --- |
| 1 | #310 | clean, 225 tests |
| 2 | #326 (carries #318) | clean, 229 |
| 3 | #331 (carries #315) | clean, 238 |
| 4 | #343 (carries #340, #333) | clean, 263 |
| 5 | #339 (carries #334) | 2-hunk conflict in `models.py` with #343 (adjacent enum edits) |
| 6 | #287 | 4-hunk conflict with #326/#331 (`client.py`, `models.py`, test) |
| 7 | #329 (carries #287) | 5 hunks; also conflicts with `main` on README |
| 8 | #307 | clean, 264 |
| 9 | #324 | clean, 266 |
| 10 | #323 | clean, 268 |
| 11 | #328 (carries #321) | clean, 272 |
| 12 | #322 | clean, 265 (removes 7 delete-attachment tests) |
| 13 | #325 (carries #322) | clean, 265 |
| 14 | #336 | 8 hunks: README, `models.py`, and the `_destructive_write_annotations` helper that #325 deleted |
| 15 | #335 | 6 hunks in `client.py`, `models.py` |
| 16 | #338 | clean, 303 tests |
| 17 | #332 | 7 hunks: `server.py`, `pyproject.toml`, `uv.lock`, test (also conflicts with `main` on the lock) |
| 18 | #341 | 3 hunks: CHANGELOG, `server.py` |
| 19 | #314 | 2 hunks in `tests/test_server.py` |
| 20 | #316 | 2 hunks in `client.py` |
| 21 | #337 | 3 hunks in `server.py` |
| 22 | #311 | 2 hunks |
| 23 | #267 | 2 hunks |
| 24 | #342 | 2 hunks in `pyproject.toml`, `uv.lock` (also conflicts with `main`) |
| 25 | #276 | clean, 303 |
| 26 | #291 | merges, but ruff 7 errors (PLR0917) and mypy 12 errors (mcp 2.x `ToolAnnotations` kwargs) |
| 27 | #306 | same lint/mypy failures inherited from #291 |

Every conflict is in a file that several PRs edit from the same base. None is a
logic collision except one, which is a deliberate choice: #325 deletes the
`_destructive_write_annotations` helper that #334, #336, #339 and #312 call. Keep
the helper.

## Decisions

These are the calls the ledger left open, decided here on the evidence above.

| Family | Decision | Close as superseded |
| --- | --- | --- |
| Ticket read (#319) | Merge **#328**. It carries #321's commit (author retained) and adds the base-URL normalisation fix. Take the `requests` and `types-requests` declarations from #327 as a one-line `pyproject.toml` edit; do not merge #327 itself. Defer #313's request-timeout feature to a follow-up issue. | #321, #327, #313 |
| Attachment removal (#320) | Merge **#322 then #325**, but keep `_destructive_write_annotations` when resolving #336. | #330 |
| Ticket merge (#309) | Merge **#336** (re-reviewed on its current head, percent-encoding fix). | #312, with credit to its author in the close comment |
| Knowledge Base (#198) | Merge **#267**. It has post-review fixes, title/body/subtree search and 21 commits of history; #344 is a single unreviewed commit with title-only search. Re-run the review on the integration branch, not the PR. | #344, #200 (630 commits, 128 conflicting files, unmergeable) |
| Stats (#345, #323, #311, #314) | Merge **#323** and **#314**. #314 needs one docstring paragraph documenting `counts_truncated`; add it in the train. Do not merge #311: its GraphQL fast path cannot activate on stock Zammad and returns different semantics from the fallback. | #311 (close with the review as the reason; the `_api_session()` refactor is worth re-submitting alone) |
| Flat schemas (#212) | Merge **#332 first**. It is one `@flat_params(Model)` decorator per tool plus a 101-line module. Every feature PR that registers a new tool gets the same one-line decorator during integration: #334, #336, #338, #267, #316. | none |
| Dependencies | Merge **#342** (deletes 13,878 lines of dead automation, tightens floors). Merge **#276** after it, dropping its edits to the workflows #342 deletes. Pin `mcp>=1.28.1,<2` and `fastmcp>=3,<4` as constraints so Renovate stops crossing majors; do the 2.x/4.x upgrade as its own PR later with the PLR0917 ignore and the `ToolAnnotations` snake_case rename. Close #291 and let Renovate reopen it against the pins. For #306, keep Python `3.13.x` (the project cap is `<3.14`) and take the tool bumps. | #264, #317 (fixes already on `main`), #291 |
| Author-action PRs | #337 (audit logging) and #316 (JSONL export) are the only ones with unresolved substantive blockers. Both are small and known: #337 needs `.env` loaded before `AuditConfig.from_env`; #316 needs the tool added to the inventory test, a README entry, and the export coroutine split. Do both in the train rather than waiting on authors; #337 is your own branch anyway. | none |
| Resilience (#341) | Author reports both requested fixes on the current head. Re-review the delta on the integration branch and merge. | none |

## Execution: four integration PRs

Do not merge the 41 PRs individually. Build four integration branches from `main`,
each opened as one PR so CI runs once per batch and a regression is bisectable to a
batch of related changes. Merge each batch before starting the next so later batches
rebase onto a green base. Contributor commits come in through `git merge`, so
authorship is preserved in history; close each original with a comment naming the
integration PR.

Run the full gate after every merge in every batch. Stop and fix at the first red.

### Batch 1: platform (target: half a day)

1. `#342` retire automation. Regenerate `uv.lock` with `uv lock` after resolving
   `pyproject.toml`; do not hand-merge the lock.
2. Add constraints `mcp>=1.28.1,<2` and `fastmcp>=3.0.0,<4` to `[tool.uv]`.
3. `#276` GitHub Actions pins, minus the three deleted workflows.
4. `#306` mise tools, with `python = "3.13.14"` kept.
5. `#332` flat tool schemas. This fixes the bug agents hit on every tool call (#212),
   which is why it leads.
6. Close #264, #317, #291. Close #289 and #257 once the batch merges.

### Batch 2: bug fixes, mostly contributor PRs (target: one day)

Order chosen so clean merges go first and the conflicting ones land on the fewest
moving parts:

`#310`, `#307`, `#324`, `#323`, `#328`, `#314` (+ docstring), `#322`, `#325`,
`#326`, `#331`, `#287`, `#329`.

Expected conflicts: #287 and #329 against #326/#331 in `client.py` and
`models.py` (adjacent field additions), and #329 against `main` in README. After merging #328,
add `requests>=2.32.0` and `types-requests` to `pyproject.toml` and drop the
`# type: ignore[import-untyped]` on the import.

Close on merge: #318, #315, #321, #327, #313 (open a follow-up issue for the
timeout), #330, and #311 (declined; see the Stats decision above).

### Batch 3: features (target: one to two days)

`#343` (enum stack), `#339` (bulk stack), `#335`, `#338`, `#336`, `#341`.

Each new tool gets `@flat_params(...)`. Restore `_destructive_write_annotations` when #336
conflicts with #325's deletion. Expected conflicts: #339 vs #343 in `models.py`
(2 hunks), #336 (8 hunks), #335 (6 hunks), #341 (3 hunks).

Close on merge: #333, #340, #334, #312. Update issues #201, #15, #278, #309, #16, #120
with the integration PR link; close the ones the MVP fully answers.

### Batch 4: the three that need code work (target: one day)

`#267` Knowledge Base, `#316` export, `#337` audit logging. Each has a concrete,
bounded fix list above. Because this batch adds the most new surface, it goes last on
a base that already has every other change.

Close on merge: #344, #200, #198 (or narrow it to the create/write follow-up).

## Mechanics and guardrails

- Work in this repo, not forks: `git fetch origin '+refs/pull/*/head:refs/remotes/pr/*'`
  gives every head locally. Fork branches cannot be pushed to, which is another reason
  not to try to fix contributor PRs in place.
- Fork PRs never ran CI. The integration PR is what gets the first real test run for
  most of this code, so treat batch CI as the gate, not the per-PR checks.
- The `main` ruleset requires zero approvals and the `test-and-coverage` and
  `security-scan` checks; its only review gate is the extra approval for
  unattributed changes, which is satisfied by committing integration work under
  the maintainer identity. Do not use an admin bypass. If a review requirement
  is ever added, wait for an independent reviewer or defer the merge.
- Do not run `scripts/quality-check.sh` during integration; it mutates files. Use the
  four non-mutating commands the ledger names.
- Keep the merge commits. Squashing the integration PR would erase contributor
  authorship, which is the whole reason for merging their branches rather than
  reimplementing.
- After batch 1, expect Renovate to reopen a lock-file PR against the new pins. That
  one should be safe to merge on green.

## Estimated outcome

| | Now | After batch 1 | After batch 4 |
| --- | --- | --- | --- |
| Open PRs | 41 | 33 | 0 |
| Integration PRs opened | 0 | 1 | 4 |
| Registered tools | 22 | 22 | ~30 |

Total effort is three to four working days for one person, most of it conflict
resolution and reading the four re-review deltas (#267, #307, #323, #341). The train
already proved the code compiles and tests together for 12 of the PRs; the remaining
work is mechanical.

## Evidence trail

- Merge train log and per-step tags: `sim-after-<pr>` on the scratch branch
  `sim/train` (local only, not pushed).
- Conflict sizing: `git merge-tree --write-tree sim-after-276 pr/<n>` and counting
  `<<<<<<<` markers in the conflicted blobs.
- Ancestry checks confirmed the ledger: #318⊂#326, #315⊂#331, #287⊂#329, #321⊂#328,
  #322⊂#325, #333⊂#340⊂#343, #334⊂#339. #307 is not an ancestor of #324 and #321 is
  not an ancestor of #327 (cherry-pick), both as the ledger states.
- `main` gate on 2026-09-29: 222 passed, ruff format/check clean, mypy clean, Python 3.13.
- `security-scan` on `main`: success on 2026-09-26 (`36275441354`) and 2026-09-28
  (`36459094274`).
