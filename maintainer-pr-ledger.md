# Maintainer PR ledger — Zammad-MCP

**Pre-triage snapshot: 2026-09-25 UTC.** This enumerates every open PR and issue in `basher83/Zammad-MCP`, ranks attention, separates decisions from implementation/review work, and proposes coherent queues. It is **not** a PR execution workflow, merge authorization, or a new code-review verdict.

**Verified coverage: 41 PRs + 16 issues = 57 open items**, reconciled by exact number sets, not just totals. Gitcrawl: 18 durable discovery clusters; curated here into 17 workgroups. Comment routing: **PRs — 11 Yes / 16 No / 14 Unclear/conditional; issues — 7 Yes / 3 No / 6 Unclear/conditional.** These are item flags, not that many separate messages: use the grouped decision inbox below.

## Read this first

1. **Preserve the existing reviews.** “Approve” in an owner-authored comment is useful technical evidence even when GitHub could not accept self-approval. It is not formal `APPROVED`. A submitted review can also be `COMMENTED` while its text says approve/request changes. Historical approval, current review decision, exact reviewed SHA and current head are separate fields in [STATUS.md](docs/maintainer/STATUS.md) and [ledger.json](docs/maintainer/ledger.json).
1. **Do not replay old requests after a fix.** #307, #323, #267, #312 and #341 have post-review changes without a later maintainer approval. In contrast, #336 and #338 were actually re-reviewed after fixes; their earlier blockers must not be revived.[20][48][50]
1. **Do not let titles substitute for current evidence.** #323 now corrects stable seeded type IDs, despite its old name-based title/body. #342 now includes plugin retirement and dependency remediation beyond its original approved removal diff.[35][54]
1. **A green list is not complete readiness.** #276/#291/#306/#342 each have 17 returned passing checks, yet #276's old approval is dismissed, #291 crosses runtime majors, #306 still proposes Python 3.14.7 against current `<3.14` policy, and #342 is conflicting with a materially expanded diff. Missing expected checks and branch rules were not waived.[14][18][19]
1. **No new permission questions from stale labels.** #333's review explicitly treats its issue label as stale; #334's review explicitly leaves scope confirmation open. The ledger honors that distinction.[45][46]

## Priority, route and comment semantics

- **P1:** existing user-visible correctness or a shared integration/policy decision that affects several queued changes. **P2:** bounded capability, follow-up or routine maintenance. **P3:** lower-urgency proposal, parked work or administrative disposition. No P0 incident is established by this evidence.
- **Rank:** suggested triage-attention order within the PR inventory; issue rank is separate. It is not a merge order. **W0:** shared platform baseline; **W1:** existing-contract corrections; **W2:** bounded capabilities; **W3:** parked/admin.
- **Comment Y:** record a concrete unanswered decision or coordination outcome before treating the family as a settled queue. **N:** no additional pre-triage comment needed; carry existing review/request/action. **U — unclear/conditional:** comment only if choosing an alternative, changing scope, acknowledging a fixed head or executing disposition. Uncertainty is not approval or queue readiness; the stated condition must be resolved before treating the affected choice as settled.
- “Maintainer comment needed” is this ledger's recommendation, not a fabricated literal field from GitHub. Evidence records distinguish explicit open questions, “None” dispositions, author proposals and absence of a verdict. **Review needed, workflow approval needed and comment needed are not synonyms.**
- `prepare` carries a reviewed candidate into later readiness work; `delta-review` limits assessment to post-review changes; `author-action` preserves existing requests; `alternative` does not enter alongside its selected competitor; `disposition` recommends administrative cleanup only.

## Concrete maintainer decision inbox

| Order | Decision / communication | Recommended outcome |
| --- | --- | --- |
| D1 | #342 / #291 / #306 / #276 shared dependency and automation baseline | Keep authorized retirement, evaluate expanded #342 separately from its old approval; prefer bounded remediation before a deliberate runtime-major migration. Preserve current Python cap unless intentionally changed; keep surviving Actions/uv pins aligned.[54][18][19] |
| D2 | #319 with #327 / #321 / #313 | Prefer #327's credited adoption, but explicitly communicate disposition of the originals and preserve #313 timeout work. Do not assume the issue's “done” narrative means merged delivery.[31][39][25] |
| D3 | #320 with #322 / #330 / #325 | Confirm removal over stub. Prefer reviewed #322 plus retained incremental follow-up; compare #330's unique autospec work, and avoid deleting a helper needed by incoming merge/bulk tools.[32][34][37] |
| D4 | #311 contract and new #345 escalation report | Answer nullable/source-labelled stats proposal; acknowledge offer of a focused escalation-deadline fix. Do not conflate either with #323's classification correction.[23][57][35] |
| D5 | #309 with #336 / updated #312 | Prefer re-reviewed #336; resolve contributor credit/supersession rather than retaining two implementations in the active queue.[21][48][24] |
| D6 | #15 / #334 | Confirm or defer the implemented one-tool bounded best-effort MVP; record once, not a new implementation plan. #339 is already-reviewed tag-bound follow-up.[2][46][51] |
| D7 | #198 with updated #267 / unreviewed #344 / parked #200 | Select one read-only carrier after comparing changed #267; preserve create/write follow-up scope. A wrapper/modular preference for #344 is not approval of its unreviewed diff.[6][13][56] |
| D8 | #278 reporters | Link reviewed hybrid implementation #335 and coordinate already-offered live validation; do not reopen a settled design choice.[15][47] |

## PR inventory — ranked, all open PRs

The action column is the next **triage handoff**, not an action performed by this report. Detailed review/head/check evidence is in [STATUS.md](docs/maintainer/STATUS.md); exact discussion links, source signals and changed paths are in [ledger.json](docs/maintainer/ledger.json). Dependency choices and stack direction are in [DEPENDENCIES.md](docs/maintainer/DEPENDENCIES.md).

| Rank | P / wave | PR / class | Route | Comment | Next triage action | Workgroup / Gitcrawl cluster | Direct review/comment evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 / W1 | [#332](https://github.com/basher83/Zammad-MCP/pull/332) Flat tool schemas | reconcile | U | Preserve existing approve comment; resolve current conflict, pin review coverage, and make incoming tools follow the flat schema. No repeat 90% coverage request.[44] | G01 / 8 | [review](https://github.com/basher83/Zammad-MCP/pull/332#issuecomment-5579569984) |
| 2 | P1 / W0 | [#342](https://github.com/basher83/Zammad-MCP/pull/342) Automation retirement + dependency remediation | reconcile | Y | Keep authorized retirement direction; assess expanded a07b044 scope and current conflict with #291/#276. Old ad7b2ac approval does not cover dependency remediation.[54] | G17 / 7 | [review](https://github.com/basher83/Zammad-MCP/pull/342#issuecomment-5579848558); [later discussion](https://github.com/basher83/Zammad-MCP/pull/342#issuecomment-5789463529) |
| 3 | P1 / W0 | [#291](https://github.com/basher83/Zammad-MCP/pull/291) Dependency major-version policy | decision | Y | Choose deliberate MCP2/FastMCP4 migration versus constrained maintenance; inspect only new-head delta against recorded requests. Current checks pass; historical failures are not current results.[18] | G17 / 11 | [review](https://github.com/basher83/Zammad-MCP/pull/291#pullrequestreview-5137739620) |
| 4 | P2 / W0 | [#306](https://github.com/basher83/Zammad-MCP/pull/306) Toolchain policy | author-action | U | Default to existing Python <3.14 policy; remove unintended 3.14.7 bump/correct update matching. A cap lift would need a separate deliberate decision, not repeat permission to preserve policy.[19] | G17 / 13 | [review](https://github.com/basher83/Zammad-MCP/pull/306#pullrequestreview-5130199234) |
| 5 | P2 / W0 | [#276](https://github.com/basher83/Zammad-MCP/pull/276) GitHub Actions maintenance | delta-review | N | Review updated pins at b42e2ab; previous approve review is DISMISSED. Retain useful pins only for workflows surviving #342.[14] | G17 / 14 | [review](https://github.com/basher83/Zammad-MCP/pull/276#pullrequestreview-5130200417) |
| 6 | P1 / W1 | [#323](https://github.com/basher83/Zammad-MCP/pull/323) Stats classification correctness | delta-review | U | Re-review 2d10298/e6398c5 fixes, not the old name-based proposal. Current patch corrects seeded type IDs; production corroboration is not re-approval.[35] | G04 / 6 | [review](https://github.com/basher83/Zammad-MCP/pull/323#pullrequestreview-5131328246); [later discussion](https://github.com/basher83/Zammad-MCP/pull/323#issuecomment-5792973451) |
| 7 | P1 / W1 | [#311](https://github.com/basher83/Zammad-MCP/pull/311) Stats API contract | decision | Y | Answer contributor proposal for nullable/source-labelled counts before requesting a rewrite; existing negative review remains until changed implementation is assessed.[23] | G04 / 15 | [review](https://github.com/basher83/Zammad-MCP/pull/311#pullrequestreview-5130214434); [later discussion](https://github.com/basher83/Zammad-MCP/pull/311#issuecomment-5589759396) |
| 8 | P1 / W1 | [#327](https://github.com/basher83/Zammad-MCP/pull/327) Canonical ticket-read fix candidate | decision | U | Prefer the later explicitly credited adoption as primary, subject to recording family disposition and resolving current conflict. Preserve its approve comment; do not silently discard #313 timeout work.[39] | G02 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/327#issuecomment-5569977822) |
| 9 | P1 / W1 | [#321](https://github.com/basher83/Zammad-MCP/pull/321) Original ticket-read fix | alternative | Y | Retain technical approval; communicate #327 adoption/credit if chosen. Do not queue both equivalent core fixes.[33] | G02 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/321#pullrequestreview-5130215418); [later discussion](https://github.com/basher83/Zammad-MCP/pull/321#issuecomment-5568383126) |
| 10 | P1 / W1 | [#313](https://github.com/basher83/Zammad-MCP/pull/313) Expanded ticket read + timeout | alternative | Y | Record primary selection; retain request-timeout feature separately if #327/#321 carries expansion. Existing approval is not a mandate to merge competing patches.[25] | G02 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/313#pullrequestreview-5130216718) |
| 11 | P1 / W1 | [#328](https://github.com/basher83/Zammad-MCP/pull/328) Ticket URL follow-up | author-action | U | Existing timeout/test-boundary requests already specify work. Settle parent and timeout scope once, then fix/port; do not repeat review text.[40] | G02 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/328#issuecomment-5569977569) |
| 12 | P1 / W1 | [#322](https://github.com/basher83/Zammad-MCP/pull/322) Unsupported attachment deletion removal | decision | Y | Confirm removal rather than stub and choose one carrier. Prefer already-reviewed #322 plus selected #325 work; evaluate #330 autospec delta separately.[34] | G03 / 4 | [review](https://github.com/basher83/Zammad-MCP/pull/322#pullrequestreview-5130191300); [later discussion](https://github.com/basher83/Zammad-MCP/pull/322#issuecomment-5568339497) |
| 13 | P1 / W1 | [#330](https://github.com/basher83/Zammad-MCP/pull/330) Alternative attachment removal | alternative | Y | No maintainer verdict found: author fixes and bot status do not inherit #322 approval. Decide carrier before first review; preserve distinct autospec work.[42] | G03 / 4 | [discussion / review gap](https://github.com/basher83/Zammad-MCP/pull/330) |
| 14 | P2 / W1 | [#325](https://github.com/basher83/Zammad-MCP/pull/325) Attachment-removal cleanup/tests | first-review | U | First disposition of bot findings is still needed if retained; do not blindly enforce bot 90% coverage claim. Select destination after removal-family decision.[37] | G03 / 4 | [discussion / review gap](https://github.com/basher83/Zammad-MCP/pull/325) |
| 15 | P1 / W1 | [#310](https://github.com/basher83/Zammad-MCP/pull/310) Prompt ticket-ID compatibility | prepare | N | Retain current-head approval; no repeated technical comment. Check the fork-workflow authorization/check gap in the later execution phase.[22] | G07 / 17 | [review](https://github.com/basher83/Zammad-MCP/pull/310#pullrequestreview-5130226791) |
| 16 | P1 / W1 | [#318](https://github.com/basher83/Zammad-MCP/pull/318) Customer update field | prepare | N | Retain current-head approval; later execution must reconcile fork CI availability. No duplicate maintainer comment needed.[30] | G05 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/318#pullrequestreview-5130212896) |
| 17 | P2 / W1 | [#326](https://github.com/basher83/Zammad-MCP/pull/326) Customer forwarding coverage | follow-up | N | Carry existing approve comment; retain only incremental test after #318. Stale owner-review label is not a missing verdict.[38] | G05 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/326#issuecomment-5569990553) |
| 18 | P1 / W1 | [#287](https://github.com/basher83/Zammad-MCP/pull/287) Pending time + attachment visibility | prepare | N | Retain repeated current-head formal approvals; #329 is non-blocking follow-up work, not a reason to re-review unchanged #287.[16] | G05 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/287#pullrequestreview-5137776976) |
| 19 | P2 / W1 | [#329](https://github.com/basher83/Zammad-MCP/pull/329) Resource attachment test/docs | author-action | N | Existing review already requests README reconciliation; current PR is conflicting. Wait for #287 then retain the small delta; no repeated request comment.[41] | G05 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/329#issuecomment-5569974915) |
| 20 | P1 / W1 | [#307](https://github.com/basher83/Zammad-MCP/pull/307) Plain-text quote preservation | delta-review | U | Human request-changes predates f9d9835 fix; assess that delta. Bot follow-up is not human approval. Broader escaping policy is optional separate work.[20] | G06 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/307#pullrequestreview-5130203584) |
| 21 | P2 / W1 | [#324](https://github.com/basher83/Zammad-MCP/pull/324) Double-quote regression coverage | follow-up | U | Keep requested-changes history and recommended parent-first sequence; old inherited defect is fixed in #307 but not included here.[36] | G06 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/324#issuecomment-5568437862) |
| 22 | P1 / W1 | [#314](https://github.com/basher83/Zammad-MCP/pull/314) Truncated stats disclosure | author-action | N | Await already-requested tool-docstring/schema and lower-bound explanation; no unresolved human question and no duplicate comment needed.[26] | G04 / 16 | [review](https://github.com/basher83/Zammad-MCP/pull/314#pullrequestreview-5131485279) |
| 23 | P2 / W2 | [#333](https://github.com/basher83/Zammad-MCP/pull/333) Case-insensitive enum inputs | prepare | N | Carry approve comment and canonical lowercase output contract. Existing review explicitly treats issue approval label as stale.[45] | G08 / 3 | [review](https://github.com/basher83/Zammad-MCP/pull/333#issuecomment-5579772220); [later discussion](https://github.com/basher83/Zammad-MCP/pull/333#issuecomment-5579778874) |
| 24 | P2 / W2 | [#340](https://github.com/basher83/Zammad-MCP/pull/340) Enum docs/rejection tests | stacked | N | Carry approve comment; integrate nested #343 into this branch before carrying reviewed follow-up into #333 if preserving current stack.[52] | G08 / 3 | [review](https://github.com/basher83/Zammad-MCP/pull/340#issuecomment-5579863828) |
| 25 | P2 / W2 | [#343](https://github.com/basher83/Zammad-MCP/pull/343) Article docstring correction | stacked | N | Carry approve comment, no new question. Leaf-first absorption avoids detaching reviewed follow-up from current branch bases.[55] | G08 / 3 | [review](https://github.com/basher83/Zammad-MCP/pull/343#issuecomment-5579895172) |
| 26 | P2 / W2 | [#335](https://github.com/basher83/Zammad-MCP/pull/335) Custom Ticket attributes | prepare | U | Approve verdict is a COMMENTED review, not formal approval. Coordinate new typed-field reservations and send reporter update on #278; do not reopen settled hybrid design.[47] | G09 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/335#pullrequestreview-5137658610) |
| 27 | P2 / W2 | [#336](https://github.com/basher83/Zammad-MCP/pull/336) Ticket merge canonical candidate | decision | Y | Prefer current-head re-reviewed #336; record attribution/disposition for #312. Do not revive fixed encoding blocker or demand redundant full review.[48] | G10 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/336#issuecomment-5579927079) |
| 28 | P2 / W2 | [#312](https://github.com/basher83/Zammad-MCP/pull/312) Original ticket merge implementation | alternative | U | Annotation blocker was fixed at 3d28c0f after review. If retained, delta-review it; if #336 chosen, communicate supersession and credit.[24] | G10 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/312#pullrequestreview-5130249534) |
| 29 | P2 / W2 | [#334](https://github.com/basher83/Zammad-MCP/pull/334) Bulk ticket update MVP | decision | Y | Existing approve comment explicitly leaves feature confirmation open. Record one-tool/bounded/best-effort scope once; #339 supplies non-blocking tag bounds.[46] | G11 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/334#issuecomment-5579761798); [later discussion](https://github.com/basher83/Zammad-MCP/pull/334#issuecomment-5579776029) |
| 30 | P2 / W2 | [#339](https://github.com/basher83/Zammad-MCP/pull/339) Bulk tag bounds | stacked | N | Carry approve comment; absorb into #334 branch before root integration if preserving stack. Unrelated stacked-CI question is not a comment blocker.[51] | G11 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/339#issuecomment-5579830399) |
| 31 | P2 / W2 | [#315](https://github.com/basher83/Zammad-MCP/pull/315) Ticket creation-date search | prepare | N | Retain current-head formal approval and existing no-human-question disposition; #331 owns header follow-up.[27] | G12 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/315#pullrequestreview-5130242450); [later discussion](https://github.com/basher83/Zammad-MCP/pull/315#issuecomment-5568439034) |
| 32 | P2 / W2 | [#331](https://github.com/basher83/Zammad-MCP/pull/331) Search result date header | follow-up | N | Carry approve comment; after #315 keep incremental header/test correction, not duplicate inherited feature diff.[43] | G12 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/331#issuecomment-5570020672) |
| 33 | P2 / W2 | [#316](https://github.com/basher83/Zammad-MCP/pull/316) Host-side JSONL export | author-action | N | Await existing inventory-test, documented export-boundary and complexity fixes. No new product comment is required by existing review.[28] | G12 / 1 | [review](https://github.com/basher83/Zammad-MCP/pull/316#pullrequestreview-5131496270) |
| 34 | P2 / W2 | [#338](https://github.com/basher83/Zammad-MCP/pull/338) HTTP-only webhook MVP | prepare | N | Carry latest approve comments at 65313d4; prior cursor blockers were fixed and re-reviewed. Preserve scoped MVP rather than asserting full #16 roadmap delivered.[50] | G13 / 9 | [review](https://github.com/basher83/Zammad-MCP/pull/338#issuecomment-5579939548) |
| 35 | P2 / W2 | [#341](https://github.com/basher83/Zammad-MCP/pull/341) Outgoing retry/rate-limit resilience | delta-review | U | Author reports both requested message fixes at e5a0e7a; queue targeted re-review, not another instruction to implement them. No subsequent approve verdict found.[53] | G14 / 5 | [review](https://github.com/basher83/Zammad-MCP/pull/341#issuecomment-5579892612); [later discussion](https://github.com/basher83/Zammad-MCP/pull/341#issuecomment-5579938141) |
| 36 | P2 / W2 | [#337](https://github.com/basher83/Zammad-MCP/pull/337) Opt-in audit logging | author-action | N | Unchanged .env bootstrap-order blocker already has clear request and tests specified. Await author fix; no duplicate comment needed.[49] | G15 / 5 | [review](https://github.com/basher83/Zammad-MCP/pull/337#pullrequestreview-5137670420) |
| 37 | P2 / W2 | [#267](https://github.com/basher83/Zammad-MCP/pull/267) Updated read-only Knowledge Base slice | decision | Y | Compare updated candidate first: historical probe/payload/type blockers have response changes. Choose between this updated head and #344, resolve Codacy policy request, then delta-review selected route.[13] | G16 / 2 | [review](https://github.com/basher83/Zammad-MCP/pull/267#pullrequestreview-5130226654) |
| 38 | P2 / W2 | [#344](https://github.com/basher83/Zammad-MCP/pull/344) Modular read-only Knowledge Base slice | alternative | Y | First maintainer review still absent. Prefer wrapper/modular design only provisionally; compare search semantics and contributor fixes in #267 before selecting.[56] | G16 / 2 | [discussion / review gap](https://github.com/basher83/Zammad-MCP/pull/344) |
| 39 | P3 / W3 | [#200](https://github.com/basher83/Zammad-MCP/pull/200) Oversized Knowledge Base CRUD | parked | U | Keep parked per existing split decision; communicate successor/ownership only when canonical read-only route is selected.[7] | G16 / 2 | [review](https://github.com/basher83/Zammad-MCP/pull/200#pullrequestreview-5130247102) |
| 40 | P3 / W3 | [#264](https://github.com/basher83/Zammad-MCP/pull/264) Superseded urllib3 bump | disposition | U | Record close-as-superseded recommendation: 5dc76d3 is on current main. Do not spend rebase work on remaining registry rewrite.[12] | G17 / 18 | [review](https://github.com/basher83/Zammad-MCP/pull/264#pullrequestreview-5130186682) |
| 41 | P3 / W3 | [#317](https://github.com/basher83/Zammad-MCP/pull/317) Superseded Semgrep fix | disposition | U | Record close-as-superseded and #260 resolved-by-c0bc500 recommendation. Both fix commit and Semgrep isolation already on main.[29] | G17 / 10 | [review](https://github.com/basher83/Zammad-MCP/pull/317#pullrequestreview-5130178192) |

## Issue inventory — ranked, all open issues

Issue implementation links below are not automatic dependency edges. Open feature umbrellas can contain deferred requirements even when a scoped PR has approval. Closed history is consulted only as resolution evidence, not included in the active inventory.

| Rank | Priority | Issue | Route / related PRs | Comment | Next triage action | Workgroup / Gitcrawl cluster | Direct review/comment evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 | [#345](https://github.com/basher83/Zammad-MCP/issues/345) get_ticket_stats: escalated_count counts future SLA deadlines, not escalated tickets | new-triage; #323, #311 | Y | Acknowledge offer of focused escalation-deadline fix/tests; no implementing PR found. Distinct from #323 and coordinate #311 semantics.[57] | G04 / 6 | See linked issue discussion |
| 2 | P1 | [#212](https://github.com/basher83/Zammad-MCP/issues/212) Flatten tool `params` into `arguments` to fix arg/param validation failures | track-pr; #332 | U | Track #332 corrected schema and new-tool integration; do not restart implementation planning. Record compatibility decision only if needed.[9] | G01 / 8 | See linked issue discussion |
| 3 | P1 | [#319](https://github.com/basher83/Zammad-MCP/issues/319) zammad_get_ticket returns "Unknown" for State, Priority, Group, Owner and Customer | choose-carrier; #327, #321, #313, #328 | Y | Resolve #327/#321/#313 carrier and timeout follow-up. Done comment/pending-close label do not prove delivery; fixes remain open.[31] | G02 / 1 | See linked issue discussion |
| 4 | P1 | [#320](https://github.com/basher83/Zammad-MCP/issues/320) zammad_delete_attachment always fails: Resource.destroy() takes 2 positional arguments but 4 were given | choose-carrier; #322, #330, #325 | Y | Confirm removal/stub once and #322 versus #330; retain unique #325 work. Whole-article deletion is a separate feature.[32] | G03 / 4 | See linked issue discussion |
| 5 | P2 | [#309](https://github.com/basher83/Zammad-MCP/issues/309) Feature request: ticket merge tool (PUT /api/v1/ticket_merge) | choose-carrier; #336, #312 | Y | Choose #336 or updated #312 and record contributor credit; do not create third implementation.[21] | G10 / 1 | See linked issue discussion |
| 6 | P2 | [#15](https://github.com/basher83/Zammad-MCP/issues/15) Feature: Implement bulk operations for tickets | scope-confirmation; #334, #339 | Y | Confirm implemented bounded single-tool best-effort MVP with tags/note; existing review explicitly leaves approval open.[2] | G11 / 1 | See linked issue discussion |
| 7 | P2 | [#278](https://github.com/basher83/Zammad-MCP/issues/278) Support custom Zammad Ticket object attributes in MCP | reporter-coordination; #335 | Y | Point reporters to reviewed #335 and their offered live validation; read/update hybrid is implemented, create excluded.[15] | G09 / 1 | See linked issue discussion |
| 8 | P2 | [#201](https://github.com/basher83/Zammad-MCP/issues/201) Make all constants case-insensitive if they can be | track-stack; #333, #340, #343 | N | Track #333/#340/#343; later review resolves enum-only scope and treats needs-approval label as stale.[8] | G08 / 3 | See linked issue discussion |
| 9 | P2 | [#198](https://github.com/basher83/Zammad-MCP/issues/198) zammad knowledgebase | choose-slice; #267, #344, #200 | Y | Choose updated #267 versus #344; preserve create/write acceptance items before read-only Closes reference retires umbrella.[6] | G16 / 2 | See linked issue discussion |
| 10 | P2 | [#16](https://github.com/basher83/Zammad-MCP/issues/16) Feature: Add webhook/real-time update support | track-pr; #338 | U | Track approved HTTP-only #338; retain deferred registration/push/user-org event requirements if closing umbrella on MVP.[3] | G13 / 9 | See linked issue discussion |
| 11 | P3 | [#120](https://github.com/basher83/Zammad-MCP/issues/120) Feature: Implement rate limiting for API requests | track-pr; #341 | U | Track fixed-head re-review of #341; broader resilience/defaults scope only needs comment if still undecided, not new planning.[4] | G14 / 5 | See linked issue discussion |
| 12 | P3 | [#121](https://github.com/basher83/Zammad-MCP/issues/121) Feature: Implement audit logging for security and compliance | track-pr; #337 | U | Track #337 author .env-order fix; distinguish low-priority feature request from defect in proposed opt-in control.[5] | G15 / 5 | See linked issue discussion |
| 13 | P2 | [#289](https://github.com/basher83/Zammad-MCP/issues/289) [triage] Zammad-MCP maintainer digest | retirement-tracking; #342, #257 | N | Removal direction already explicitly authorized; track expanded #342 assessment and close only after producer removal lands.[17] | G17 / 7 | See linked issue discussion |
| 14 | P3 | [#260](https://github.com/basher83/Zammad-MCP/issues/260) fix: uv run semgrep broken on Python 3.13 (pkg_resources missing) | disposition; #317 | U | Record resolved-by-c0bc500 / #259 closure recommendation and superseded #317. No repeated diagnosis needed.[11] | G17 / 10 | See linked issue discussion |
| 15 | P3 | [#257](https://github.com/basher83/Zammad-MCP/issues/257) [triage] Zammad-MCP maintainer digest | legacy-artifact; #342, #289 | U | Separate still-open same-title digest; include in retirement cleanup after producer removal. #289 directive did not explicitly name it.[10] | G17 / unclustered | See linked issue discussion |
| 16 | P3 | [#3](https://github.com/basher83/Zammad-MCP/issues/3) Dependency Dashboard | dashboard; #291, #306, #276, #342 | N | Keep Renovate control dashboard open; actual version decisions belong with #291/#306/#276. Do not click approval controls here.[1] | G17 / 12 | See linked issue discussion |

## Queue entry recommendations

- **Already-reviewed, no new discussion needed:** begin later readiness preparation for #310, #318 and #287; preserve approved incremental #326 and #331 after their parents. Carry enum stack verdicts and latest webhook approval rather than asking for another full review.[22][30][16]
- **High-priority changed-head assessment:** #323 and #307; #332 needs conflict resolution plus reviewed-head reconciliation rather than another generic schema debate.[35][20][44]
- **Do not queue both alternatives:** expansion (#327/#321/#313), deletion (#322/#330), ticket merge (#336/#312), read-only KB (#267/#344). Distinct follow-up work must survive any supersession.[39][42][48]
- **Already-actionable author lane:** #314, #316, #337 and #329; #328 also needs parent/timeout coordination. Repeating existing requested changes is not useful maintainer work.[26][28][49]
- **Administrative recommendations, not performed:** supersede #264 and #317 using fixes already on main; retire #257/#289 only after the digest producer is removed. Keep Renovate dashboard #3 open.[12][29][1]

## Fresh completion verification

Reconciled at **2026-09-25T08:05:38.952807+00:00**. `gitcrawl threads basher83/Zammad-MCP --limit 10000 --json` returned **339 / 339 archived rows**, confirmed against read-only SQLite count; filtering `state=open` produced **41 PRs + 16 issues = 57**. Gitcrawl exposes a limit, not a cursor: the above-limit proof confirms the listing is untruncated. Fresh GitHub GraphQL connections independently returned **41/41 PRs and 16/16 issues**, both with **`hasNextPage=false`**. Missing, extra and duplicate item sets are all empty.

All **41 PR classifications** were checked against freshly force-fetched comments/reviews: no discussion/body or head changes from the analyzed evidence. Explicit requests, inferred decisions and unclear/conditional cases retain separate evidence. The REST aggregate still omits #257; targeted lookup/sync plus the complete GraphQL issue connection confirm it remains OPEN and is included here.

Evidence: [coverage-verification.json](docs/maintainer/coverage-verification.json), including one classification check per PR; [gitcrawl-open-inventory.json](docs/maintainer/gitcrawl-open-inventory.json), the complete normalized open set. The older detailed check timestamps below remain identified rather than being presented as newly rerun CI.

## Collection, verification and limitations

Gitcrawl sync with comments/PR details completed at 2026-09-25T07:40:41.802145Z; live `gh pr view`/`gh pr checks` observations span 2026-09-25T07:43:21.521751+00:00 to 2026-09-25T07:43:32.436390+00:00. All 41 live PR heads match hydrated detail heads. Both `gh pr list` and `gh issue list` inventories were reconciled with the archive. The default open scan omitted #257; targeted `gh issue view`, REST and Gitcrawl sync confirmed it OPEN and restored it to this inventory. Open-item creation dates span 2025-07-08T03:07:42Z to 2026-09-23T10:13:18Z; most recent item update is 2026-09-25T07:19:47Z.

Discussion coverage: {'issue_comment': 185, 'pull_review': 68, 'pull_review_comment': 83}; 68 review threads were hydrated. Existing clusters were retained as discovery evidence, not recomputed into assumed duplicate verdicts. Local code inspection confirmed current main policy and the already-landed resolution commits for #264/#317; local code/test execution was not part of this task. Some archived force-push commit rows are historical, so commit-ancestry comparisons use current fetched-at membership only.

The ledger does not claim current local test execution, new bug reproduction, branch-rule satisfaction, complete bot review or correctness of a combined branch. Existing reviewers' results are attributed to their source/head. All GitHub operations were read-only; no comments, labels, issue closures, workflow approvals, PR branch changes or merges were performed.

## Companion files

- [DEPENDENCIES.md](docs/maintainer/DEPENDENCIES.md): canonical choices, true base stacks, content ancestry, semantic collisions, curated workgroups and raw Gitcrawl memberships.
- [STATUS.md](docs/maintainer/STATUS.md): every PR's current head, reviewed head, source verdict and current reported checks/mergeability.
- [ledger.csv](docs/maintainer/ledger.csv): one filterable row per open item.
- [ledger.json](docs/maintainer/ledger.json): structured inventory, exact source links/excerpts, current checks, file overlaps and dependency evidence.

## Workgroup rationale

Workgroup IDs map to the curated families and raw Gitcrawl memberships in [DEPENDENCIES.md](docs/maintainer/DEPENDENCIES.md). Priority follows user-visible correctness, shared integration reach, then review maturity and effort to resolve the next blocker. Higher rank does not imply greater severity or permission to bypass unresolved decisions. Each row’s next action states its item-specific rationale and preserves existing review work.

## Sources

[1] https://github.com/basher83/Zammad-MCP/issues/3
[2] https://github.com/basher83/Zammad-MCP/issues/15
[3] https://github.com/basher83/Zammad-MCP/issues/16
[4] https://github.com/basher83/Zammad-MCP/issues/120
[5] https://github.com/basher83/Zammad-MCP/issues/121
[6] https://github.com/basher83/Zammad-MCP/issues/198
[7] https://github.com/basher83/Zammad-MCP/pull/200
[8] https://github.com/basher83/Zammad-MCP/issues/201
[9] https://github.com/basher83/Zammad-MCP/issues/212
[10] https://github.com/basher83/Zammad-MCP/issues/257
[11] https://github.com/basher83/Zammad-MCP/issues/260
[12] https://github.com/basher83/Zammad-MCP/pull/264
[13] https://github.com/basher83/Zammad-MCP/pull/267
[14] https://github.com/basher83/Zammad-MCP/pull/276
[15] https://github.com/basher83/Zammad-MCP/issues/278
[16] https://github.com/basher83/Zammad-MCP/pull/287
[17] https://github.com/basher83/Zammad-MCP/issues/289
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
[31] https://github.com/basher83/Zammad-MCP/issues/319
[32] https://github.com/basher83/Zammad-MCP/issues/320
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
