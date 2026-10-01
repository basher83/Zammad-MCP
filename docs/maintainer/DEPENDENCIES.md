# Dependency and overlap map

> **Status:** Historical snapshot. PRs #346, #347, #348, and #349 merged on 2026-09-29 and executed this triage. On 2026-09-30 the repository had no open PRs. Do not use this page as the current PR state.

This is queue design, not instructions to execute a PR workflow. Arrows below are explicitly typed; a shared filename or Gitcrawl similarity score is not proof of a dependency. Canonical choices are recommendations, not GitHub dispositions already performed.

## Recommended queue shape

- **W0 — settle shared platform drift:** reconcile #342's expanded retirement/security scope and conflict, choose #291's runtime-major policy, correct #306's Python-policy mismatch, and retain #276 pins for surviving workflows. These are related changes, not four independent routine bot merges.[54][18][19]
- **W1 — existing-contract corrections:** resolve #332's schema conflict and review coverage; delta-review #323 and #307; select ticket-read and attachment-removal carriers. Already-reviewed #310, #318 and #287 can enter preparation without fresh discussion while the decisions proceed. Do not block their triage on unrelated feature choices.[44][35][20]
- **W2 — bounded features and follow-ups:** carry approved enum stack, custom attributes, date search and webhook MVP; decide merge/bulk/KB ownership and scope; handle #341's fixed-head re-review. Keep unchanged requested-changes work with authors rather than consuming another full review.[45][47][50]
- **W3 — parked or administrative:** retain #200 as split-source material; recommend superseded dispositions for #264/#317, and retire old digests only once producer removal lands. No closing is performed by this ledger.[7][12][29]

Waves are integration preferences, not blanket hard blockers. There is no requirement to finish every W0 policy discussion before assessing an independent W1 diff. The PR ledger rank is order of **triage attention**, not an unconditional merge train. Scope severity, readiness and next owner remain separate fields.

## Canonical-choice recommendations

| Family | Recommendation | Evidence and decision still needed |
| --- | --- | --- |
| Ticket read | Prefer #327's explicitly credited adoption of #321; resolve its present conflict rather than create another implementation. | #327 says it supersedes #321 and the expansion portion of #313. Record that disposition across the family; retain #313 timeout work separately. #321/#313 remain technically approved alternatives, not rejected fixes.[39][33][25] |
| Attachment removal | Prefer already-reviewed #322 as carrier; retain selected #325 cleanup/tests, and assess #330's resource-autospec delta separately. | #330 claims supersession but has no maintainer verdict; it is not a complete superset of #325. Confirm remove-versus-stub once. Choosing #330 instead is viable but requires its own first review.[34][37][42] |
| Ticket merge | Prefer #336, whose encoding fix has current-head re-review approval in comments. | #312 also fixed its annotation blocker after review and is narrower; do not describe it as still carrying that defect. Decide credit/supersession rather than merge both.[48][24][21] |
| Knowledge Base | Provisionally favor #344's wrappers/modular design, **not ready-to-queue as approved**. Compare updated #267 before committing to that choice. | #267 has post-review fixes plus title/body/subtree search; #344 has title-only search and no maintainer verdict. Neither implements the create/write part of #198. Preserve that work before closing its umbrella.[56][13][6] |
| Dependency remediation | Prefer a bounded remediation/removal baseline before a separate deliberate runtime-major upgrade. | Current #342 and #291 take different runtime-major routes and overlap the lock. Both have passing returned checks; neither those checks nor #342's old approval settles the policy/integration choice.[54][18] |

## Actual base-branch stacks

| Root | Child and current target | Recommended absorption if preserving this topology |
| --- | --- | --- |
| #333 → main | #340 → `factory/issue-201`; #343 → `factory/review-followups-pr-333` | **#343 into #340, then #340 into #333, then root into main.** This is leaf-first absorption into existing target branches, not #343 directly into main.[45][52][55] |
| #334 → main | #339 → `factory/issue-15` | **#339 into #334, then root into main**, after scope confirmation.[46][51] |

These base relationships were verified with fresh `gh pr view` and archived raw PR metadata. Follow-up titles alone were not used to infer them.

## Content-dependent follow-ups that actually target main

| Parent before incremental follow-up | Proof / caveat |
| --- | --- |
| #287 → #329 | #329 contains #287's current commit set plus follow-up; README conflict remains. Parent's repeated approvals do not approve child.[16][41] |
| #318 → #326 | Both #318 commits appear in #326, plus its test. Retain only test delta after parent.[30][38] |
| #315 → #331 | Exact #315 head `69d3cfd` is present in #331 plus header/fixture commit.[27][43] |
| #307 → #324 | #324 contains old `57d014f`, **not** current corrective `f9d9835`. Parent-first recommendation requires reconciling that missing fix.[20][36] |
| #321 → #328 | Exact #321 head `5b529fd` is present in #328. #327 cherry-picked it under a different SHA; #328 is not already stacked on #327.[33][40][39] |
| #322 → #325 | Exact `cec2851` is in #325. #330 is an independent implementation, not this stack's parent.[34][37][42] |

A shared commit proves content ancestry, not that both cumulative PR diffs should be applied unchanged. No rebase, retargeting or merge is performed here.

## Semantic overlaps that change queue planning

| Overlap | Why it matters | Queue consequence |
| --- | --- | --- |
| #325 ↔ #312/#334/#336 (and parked #200) | #325 deletes `_destructive_write_annotations`; the others add calls to that same helper. This is directly visible in archived patches, not merely a shared-file guess. | Preserve/reintroduce the shared annotation capability or revise cleanup when integrating the chosen features; do not accept 'orphaned' as a timeless property. This is an integration constraint, not a new standalone rejection of #325.[37][24][46] |
| #332 ↔ #334/#338 | #332 flattens registered tool schemas; the feature patches add `params: BulkTicketUpdateParams` / `params: ListEventsParams` registration. | Prefer establishing the schema baseline before integrating these tools, or explicitly forward-port it afterward. This is recommended integration order, not proof those PRs cannot be reviewed independently.[44][46][50] |
| #335 ↔ #318/#287 | Custom-field validation must distinguish typed built-ins such as customer/pending_time as those fields arrive. | Integrate typed-field fixes first where practical, then reconcile reserved-name handling; do not infer a hard dependency from shared models alone.[47][30][16] |
| #311 ↔ #323/#314/#345 | Stats categorization, truncation disclosure, source-dependent semantics and escalation deadlines are different concerns on one public result. | Queue #323 corrected-ID delta and #314 disclosure separately; answer #311 contract question; keep #345 as its own reported defect. #323 does not resolve #345.[23][35][57] |
| #315/#331 ↔ #316 | Independent patches add overlapping client date-query arguments, but #316 is not the complete date-search feature. | Prefer approved search contract first; reconcile export delta after author fixes. No requirement for #313 before export is established.[27][43][28] |
| #342 ↔ #276 | #342 deletes triage workflows that #276 updates, and both touch security workflow. | After retirement direction is fixed, preserve updates to surviving workflows without resurrecting retired ones.[54][14] |
| #342 ↔ #291 (also #327 lock) | Targeted security floors/removal and broad regenerated dependency versions compete in `uv.lock`; #327 adds direct dependency declarations. | Settle dependency strategy/declarations before regenerating a combined lock; do not concatenate independent lock deltas.[54][18][39] |
| #335/#338/#337 | Some CI/lifecycle surfaces overlap, but custom attributes, HTTP events and audit logging are independent capabilities. | Coordinate shared changes; do not invent feature prerequisites.[47][50][49] |
| #341 ↔ bulk/export/webhooks | Outbound resilience is not webhook-ingress protection, and no hard dependency from those PRs was established. | Do not hold bounded bulk/export or webhook triage waiting for #341 merely because all involve request volume.[53][46][50] |

## No redundant maintainer-comment queue

- Existing **“Requested changes: None / Open questions: None”** or equivalent resolved dispositions support carrying the verdict for #287, #326, #331, #333, #340, #343 and latest #338. They are not literal promises that no future integration discussion can ever be needed.[16][38][50]
- #310/#318's historical request to approve fork Actions runs is a **maintainer action**, not a missing explanatory comment. The ledger retains current check observations separately.[22][30]
- #314/#316/#337 already have actionable requested changes and no required product answer. The next owner is the author, not a maintainer asked to restate feedback.[26][28][49]
- #307/#323/#267/#312/#341 received fixes after the negative review. They need focused disposition if selected, not a repeated demand for already-submitted changes. Optional acknowledgment is marked conditional rather than manufacturing an approval gate.[20][35][53]
- Stale `needs:owner-review` / `status: needs approval` labels are contextual only. #333's review explicitly calls the issue label stale; #334's review explicitly leaves feature confirmation open. These receive different routing.[45][46]

## Gitcrawl discovery versus curated groups

Gitcrawl's 18 durable groups cover 56 items; #257 was recovered separately and has no membership in that clustering run. Cluster 1 is a 22-item connected topic group spanning distinct fixes and features, not a duplicate set. Cluster 5 joins outgoing resilience with auditing even though neither depends on the other. Conversely, statistics are split among clusters 6, 15 and 16. Curated workgroups below correct those coarse boundaries without changing archive cluster overrides.

The full filename-intersection pairs live in `ledger.json` as candidate overlap evidence. File overlap is deliberately not encoded as a hard dependency.

### Curated workgroups

| Group | Scope | Members |
| --- | --- | --- |
| G01 | Flat schema | [#212](https://github.com/basher83/Zammad-MCP/issues/212), [#332](https://github.com/basher83/Zammad-MCP/pull/332) |
| G02 | Ticket read | [#319](https://github.com/basher83/Zammad-MCP/issues/319), [#313](https://github.com/basher83/Zammad-MCP/pull/313), [#321](https://github.com/basher83/Zammad-MCP/pull/321), [#327](https://github.com/basher83/Zammad-MCP/pull/327), [#328](https://github.com/basher83/Zammad-MCP/pull/328) |
| G03 | Attachment removal | [#320](https://github.com/basher83/Zammad-MCP/issues/320), [#322](https://github.com/basher83/Zammad-MCP/pull/322), [#325](https://github.com/basher83/Zammad-MCP/pull/325), [#330](https://github.com/basher83/Zammad-MCP/pull/330) |
| G04 | Stats contracts | [#345](https://github.com/basher83/Zammad-MCP/issues/345), [#323](https://github.com/basher83/Zammad-MCP/pull/323), [#311](https://github.com/basher83/Zammad-MCP/pull/311), [#314](https://github.com/basher83/Zammad-MCP/pull/314) |
| G05 | Typed update fields / attachments | [#287](https://github.com/basher83/Zammad-MCP/pull/287), [#318](https://github.com/basher83/Zammad-MCP/pull/318), [#326](https://github.com/basher83/Zammad-MCP/pull/326), [#329](https://github.com/basher83/Zammad-MCP/pull/329) |
| G06 | Plain text | [#307](https://github.com/basher83/Zammad-MCP/pull/307), [#324](https://github.com/basher83/Zammad-MCP/pull/324) |
| G07 | Prompt IDs | [#310](https://github.com/basher83/Zammad-MCP/pull/310) |
| G08 | Case-insensitive enums | [#201](https://github.com/basher83/Zammad-MCP/issues/201), [#333](https://github.com/basher83/Zammad-MCP/pull/333), [#340](https://github.com/basher83/Zammad-MCP/pull/340), [#343](https://github.com/basher83/Zammad-MCP/pull/343) |
| G09 | Custom fields | [#278](https://github.com/basher83/Zammad-MCP/issues/278), [#335](https://github.com/basher83/Zammad-MCP/pull/335) |
| G10 | Ticket merge | [#309](https://github.com/basher83/Zammad-MCP/issues/309), [#312](https://github.com/basher83/Zammad-MCP/pull/312), [#336](https://github.com/basher83/Zammad-MCP/pull/336) |
| G11 | Bulk updates | [#15](https://github.com/basher83/Zammad-MCP/issues/15), [#334](https://github.com/basher83/Zammad-MCP/pull/334), [#339](https://github.com/basher83/Zammad-MCP/pull/339) |
| G12 | Search / export | [#315](https://github.com/basher83/Zammad-MCP/pull/315), [#331](https://github.com/basher83/Zammad-MCP/pull/331), [#316](https://github.com/basher83/Zammad-MCP/pull/316) |
| G13 | Webhook events | [#16](https://github.com/basher83/Zammad-MCP/issues/16), [#338](https://github.com/basher83/Zammad-MCP/pull/338) |
| G14 | Outgoing resilience | [#120](https://github.com/basher83/Zammad-MCP/issues/120), [#341](https://github.com/basher83/Zammad-MCP/pull/341) |
| G15 | Audit logging | [#121](https://github.com/basher83/Zammad-MCP/issues/121), [#337](https://github.com/basher83/Zammad-MCP/pull/337) |
| G16 | Knowledge Base | [#198](https://github.com/basher83/Zammad-MCP/issues/198), [#200](https://github.com/basher83/Zammad-MCP/pull/200), [#267](https://github.com/basher83/Zammad-MCP/pull/267), [#344](https://github.com/basher83/Zammad-MCP/pull/344) |
| G17 | Platform / maintenance / retirement | [#3](https://github.com/basher83/Zammad-MCP/issues/3), [#291](https://github.com/basher83/Zammad-MCP/pull/291), [#276](https://github.com/basher83/Zammad-MCP/pull/276), [#306](https://github.com/basher83/Zammad-MCP/pull/306), [#264](https://github.com/basher83/Zammad-MCP/pull/264), [#260](https://github.com/basher83/Zammad-MCP/issues/260), [#317](https://github.com/basher83/Zammad-MCP/pull/317), [#257](https://github.com/basher83/Zammad-MCP/issues/257), [#289](https://github.com/basher83/Zammad-MCP/issues/289), [#342](https://github.com/basher83/Zammad-MCP/pull/342) |

### Preserved archive cluster membership

| ID | Stable slug | Members |
| --- | --- | --- |
| 1 | `final-target-able-mqst` | [#15](https://github.com/basher83/Zammad-MCP/issues/15), [#278](https://github.com/basher83/Zammad-MCP/issues/278), [#287](https://github.com/basher83/Zammad-MCP/pull/287), [#307](https://github.com/basher83/Zammad-MCP/pull/307), [#309](https://github.com/basher83/Zammad-MCP/issues/309), [#312](https://github.com/basher83/Zammad-MCP/pull/312), [#313](https://github.com/basher83/Zammad-MCP/pull/313), [#315](https://github.com/basher83/Zammad-MCP/pull/315), [#316](https://github.com/basher83/Zammad-MCP/pull/316), [#318](https://github.com/basher83/Zammad-MCP/pull/318), [#319](https://github.com/basher83/Zammad-MCP/issues/319), [#321](https://github.com/basher83/Zammad-MCP/pull/321), [#324](https://github.com/basher83/Zammad-MCP/pull/324), [#326](https://github.com/basher83/Zammad-MCP/pull/326), [#327](https://github.com/basher83/Zammad-MCP/pull/327), [#328](https://github.com/basher83/Zammad-MCP/pull/328), [#329](https://github.com/basher83/Zammad-MCP/pull/329), [#331](https://github.com/basher83/Zammad-MCP/pull/331), [#334](https://github.com/basher83/Zammad-MCP/pull/334), [#335](https://github.com/basher83/Zammad-MCP/pull/335), [#336](https://github.com/basher83/Zammad-MCP/pull/336), [#339](https://github.com/basher83/Zammad-MCP/pull/339) |
| 2 | `orbit-ledger-daily-nz4z` | [#198](https://github.com/basher83/Zammad-MCP/issues/198), [#200](https://github.com/basher83/Zammad-MCP/pull/200), [#267](https://github.com/basher83/Zammad-MCP/pull/267), [#344](https://github.com/basher83/Zammad-MCP/pull/344) |
| 3 | `packet-credit-logic-so8z` | [#201](https://github.com/basher83/Zammad-MCP/issues/201), [#333](https://github.com/basher83/Zammad-MCP/pull/333), [#340](https://github.com/basher83/Zammad-MCP/pull/340), [#343](https://github.com/basher83/Zammad-MCP/pull/343) |
| 4 | `radar-buffer-select-mtvl` | [#320](https://github.com/basher83/Zammad-MCP/issues/320), [#322](https://github.com/basher83/Zammad-MCP/pull/322), [#325](https://github.com/basher83/Zammad-MCP/pull/325), [#330](https://github.com/basher83/Zammad-MCP/pull/330) |
| 5 | `chance-region-bonus-zfzo` | [#120](https://github.com/basher83/Zammad-MCP/issues/120), [#121](https://github.com/basher83/Zammad-MCP/issues/121), [#337](https://github.com/basher83/Zammad-MCP/pull/337), [#341](https://github.com/basher83/Zammad-MCP/pull/341) |
| 6 | `maple-space-switch-r28r` | [#323](https://github.com/basher83/Zammad-MCP/pull/323), [#345](https://github.com/basher83/Zammad-MCP/issues/345) |
| 7 | `apple-merge-object-gs75` | [#289](https://github.com/basher83/Zammad-MCP/issues/289), [#342](https://github.com/basher83/Zammad-MCP/pull/342) |
| 8 | `index-offset-charge-9osn` | [#212](https://github.com/basher83/Zammad-MCP/issues/212), [#332](https://github.com/basher83/Zammad-MCP/pull/332) |
| 9 | `cipher-relay-echo-772v` | [#16](https://github.com/basher83/Zammad-MCP/issues/16), [#338](https://github.com/basher83/Zammad-MCP/pull/338) |
| 10 | `border-steady-admin-qisi` | [#260](https://github.com/basher83/Zammad-MCP/issues/260), [#317](https://github.com/basher83/Zammad-MCP/pull/317) |
| 11 | `ember-thread-pixel-95gz` | [#291](https://github.com/basher83/Zammad-MCP/pull/291) |
| 12 | `atlas-canal-subtle-6642` | [#3](https://github.com/basher83/Zammad-MCP/issues/3) |
| 13 | `planet-chart-stream-lz0f` | [#306](https://github.com/basher83/Zammad-MCP/pull/306) |
| 14 | `online-draft-amber-kjbx` | [#276](https://github.com/basher83/Zammad-MCP/pull/276) |
| 15 | `stone-center-spiral-9920` | [#311](https://github.com/basher83/Zammad-MCP/pull/311) |
| 16 | `layer-acid-shadow-q1u8` | [#314](https://github.com/basher83/Zammad-MCP/pull/314) |
| 17 | `cycle-plain-audio-i06w` | [#310](https://github.com/basher83/Zammad-MCP/pull/310) |
| 18 | `batch-draft-second-6up6` | [#264](https://github.com/basher83/Zammad-MCP/pull/264) |

## Evidence boundaries

Existing review test counts and live-instance claims belong to their authors and reviewed SHAs; this ledger does not rerun PR code or reproduce bugs. The current-head patches were inspected only to establish changed-review state, ancestry, alternatives and integration overlap. Local `main` and GitHub `main` matched `ed8ad87dc4c0773be51c758f66d265565c969c98` during collection. Mergeability/checks are point-in-time observations, not proof of combined-branch correctness.

## Sources

[6] https://github.com/basher83/Zammad-MCP/issues/198
[7] https://github.com/basher83/Zammad-MCP/pull/200
[12] https://github.com/basher83/Zammad-MCP/pull/264
[13] https://github.com/basher83/Zammad-MCP/pull/267
[14] https://github.com/basher83/Zammad-MCP/pull/276
[16] https://github.com/basher83/Zammad-MCP/pull/287
[18] https://github.com/basher83/Zammad-MCP/pull/291
[19] https://github.com/basher83/Zammad-MCP/pull/306
[20] https://github.com/basher83/Zammad-MCP/pull/307
[21] https://github.com/basher83/Zammad-MCP/issues/309
[22] https://github.com/basher83/Zammad-MCP/pull/310
[23] https://github.com/basher83/Zammad-MCP/pull/311
[24] https://github.com/basher83/Zammad-MCP/pull/312
[25] https://github.com/basher83/Zammad-MCP/pull/313
[26] https://github.com/basher83/Zammad-MCP/pull/314
[27] https://github.com/basher83/Zammad-MCP/pull/315
[28] https://github.com/basher83/Zammad-MCP/pull/316
[29] https://github.com/basher83/Zammad-MCP/pull/317
[30] https://github.com/basher83/Zammad-MCP/pull/318
[33] https://github.com/basher83/Zammad-MCP/pull/321
[34] https://github.com/basher83/Zammad-MCP/pull/322
[35] https://github.com/basher83/Zammad-MCP/pull/323
[36] https://github.com/basher83/Zammad-MCP/pull/324
[37] https://github.com/basher83/Zammad-MCP/pull/325
[38] https://github.com/basher83/Zammad-MCP/pull/326
[39] https://github.com/basher83/Zammad-MCP/pull/327
[40] https://github.com/basher83/Zammad-MCP/pull/328
[41] https://github.com/basher83/Zammad-MCP/pull/329
[42] https://github.com/basher83/Zammad-MCP/pull/330
[43] https://github.com/basher83/Zammad-MCP/pull/331
[44] https://github.com/basher83/Zammad-MCP/pull/332
[45] https://github.com/basher83/Zammad-MCP/pull/333
[46] https://github.com/basher83/Zammad-MCP/pull/334
[47] https://github.com/basher83/Zammad-MCP/pull/335
[48] https://github.com/basher83/Zammad-MCP/pull/336
[49] https://github.com/basher83/Zammad-MCP/pull/337
[50] https://github.com/basher83/Zammad-MCP/pull/338
[51] https://github.com/basher83/Zammad-MCP/pull/339
[52] https://github.com/basher83/Zammad-MCP/pull/340
[53] https://github.com/basher83/Zammad-MCP/pull/341
[54] https://github.com/basher83/Zammad-MCP/pull/342
[55] https://github.com/basher83/Zammad-MCP/pull/343
[56] https://github.com/basher83/Zammad-MCP/pull/344
[57] https://github.com/basher83/Zammad-MCP/issues/345
