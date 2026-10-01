# Current-head and existing-review evidence

> **Status:** Historical snapshot. PRs #346, #347, #348, and #349 merged on 2026-09-29 and executed this triage. On 2026-09-30 the repository had no open PRs. Do not use this page as the current PR state.

Repository: basher83/Zammad-MCP. Snapshot window: 2026-09-25T07:43:21.521751+00:00 — 2026-09-25T07:43:32.436390+00:00.

This is a record of existing verdicts, not a new review. Blank GitHub reviewDecision does not erase approval text; COMMENTED and DISMISSED are not APPROVED. Check counts include only returned checks. All-pass does not assert expected/required workflow completeness. Exact check links and discussion excerpts are in ledger.json.

| PR | Current / reviewed SHA | Existing verdict | Current mergeability / reviewDecision | Returned check buckets |
| --- | --- | --- | --- | --- |
| [#332](https://github.com/basher83/Zammad-MCP/pull/332) | `8de7659b` / `not pinned` | Approve verdict in owner issue comment; not formal approval. Registered-tool test and constraints findings addressed; bot withdrew its 90% coverage demand.[44] | CONFLICTING / (blank) | {'pass': 16, 'fail': 1} |
| [#342](https://github.com/basher83/Zammad-MCP/pull/342) | `a07b0443` / `ad7b2ac40288` | Approve verdict posted as COMMENT on ad7b2ac (same-author fallback), not formal approval. Current a07b044 adds two later commits.[54] | CONFLICTING / (blank) | {'pass': 17} |
| [#291](https://github.com/basher83/Zammad-MCP/pull/291) | `4447daea` / `00848ce47813` | Two formal CHANGES_REQUESTED reviews: c11d83f then 00848ce. Latest recorded re-review retains PLR0917 blocker and adds MCP2/FastMCP4 ToolAnnotations typing/lower-bound mismatch. Current 4447daea newer again.[18] | MERGEABLE / CHANGES_REQUESTED | {'pass': 17} |
| [#306](https://github.com/basher83/Zammad-MCP/pull/306) | `8173302e` / `ea1422a02eda` | Formal CHANGES_REQUESTED at ea1422a; current 8173302 newer.[19] | MERGEABLE / CHANGES_REQUESTED | {'pass': 17} |
| [#276](https://github.com/basher83/Zammad-MCP/pull/276) | `b42e2ab4` / `a90e5135a9c6` | Review text says approve at a90e513, but recorded formal state is DISMISSED. Current b42e2ab is not reviewed by that approval.[14] | MERGEABLE / (blank) | {'pass': 17} |
| [#323](https://github.com/basher83/Zammad-MCP/pull/323) | `e6398c5e` / `20f42fbacd8e` | CHANGES_REQUESTED on 20f42fb; author correction 2d10298 and doc-only e6398c5 are later; production corroboration is not maintainer re-approval.[35] | MERGEABLE / CHANGES_REQUESTED | {'pass': 4} |
| [#311](https://github.com/basher83/Zammad-MCP/pull/311) | `31edfd60` / `31edfd60c4c6` | CHANGES_REQUESTED; author subsequently asks for contract agreement; no rewrite or re-review recorded.[23] | MERGEABLE / CHANGES_REQUESTED | {'pass': 4} |
| [#327](https://github.com/basher83/Zammad-MCP/pull/327) | `d08362e9` / `d08362e9121d` | Approve verdict as issue comment at d08362e, not formal APPROVED; no unresolved substantive finding in existing review.[39] | CONFLICTING / (blank) | {'fail': 2, 'pass': 15} |
| [#321](https://github.com/basher83/Zammad-MCP/pull/321) | `5b529fd8` / `5b529fd8789f` | Formal APPROVED at 5b529fd. Later #327 states core fix cherry-picked with author credit and supersedes #321.[33] | MERGEABLE / (blank) | {'fail': 1, 'pass': 3} |
| [#313](https://github.com/basher83/Zammad-MCP/pull/313) | `54d04ea6` / `54d04ea6c45e` | Formal APPROVED at 54d04ea, with explicit maintainer choice between #313 and #321; no correctness rejection.[25] | MERGEABLE / (blank) | {'fail': 1, 'pass': 3} |
| [#328](https://github.com/basher83/Zammad-MCP/pull/328) | `e8625997` / `e8625997ffec` | Request-changes verdict via issue comment at e862599; timeout and test mock/DI findings confirmed in that review.[40] | MERGEABLE / (blank) | {'fail': 2, 'pass': 15} |
| [#322](https://github.com/basher83/Zammad-MCP/pull/322) | `cec28519` / `cec2851984fb` | Formal APPROVED at cec2851; removal accepted, with maintainer remove-vs-stub choice remaining.[34] | MERGEABLE / (blank) | {'fail': 1, 'pass': 3} |
| [#330](https://github.com/basher83/Zammad-MCP/pull/330) | `99224d2b` / `not pinned` | No maintainer-account review verdict found. Author reports Codacy docstring fix in 99224d2; Codacy now zero issues; CodeRabbit rate-limited on that head.[42] | MERGEABLE / (blank) | {'pass': 16, 'fail': 1} |
| [#325](https://github.com/basher83/Zammad-MCP/pull/325) | `ef2caa3a` / `ef2caa3a425c` | No maintainer-account verdict found. CodeRabbit COMMENTED at ef2caa3 with two Major findings: 90% coverage and actual registry assertions.[37] | MERGEABLE / (blank) | {'fail': 2, 'pass': 15} |
| [#310](https://github.com/basher83/Zammad-MCP/pull/310) | `e7003087` / `e7003087ba3f` | Formal APPROVED at e700308; PT006 addressed; 90% coverage demand explicitly refuted in existing maintainer-account review.[22] | MERGEABLE / (blank) | {'fail': 1, 'pass': 3} |
| [#318](https://github.com/basher83/Zammad-MCP/pull/318) | `57bba973` / `57bba97321d0` | Formal APPROVED at 57bba97; positional compatibility and boundaries addressed; min_length demand refuted.[30] | MERGEABLE / (blank) | {'pass': 4} |
| [#326](https://github.com/basher83/Zammad-MCP/pull/326) | `80daf3ad` / `80daf3adbc9f` | Approve verdict as issue comment, not formal APPROVED; same-account formal review rejected; head 80daf3a.[38] | MERGEABLE / (blank) | {'pass': 16, 'fail': 1} |
| [#287](https://github.com/basher83/Zammad-MCP/pull/287) | `6350eef5` / `6350eef5c76d` | Formal APPROVED three times on unchanged head; latest 2026-09-08T05:41:07Z against then-base 53ad068.[16] | MERGEABLE / (blank) | {'pass': 9} |
| [#329](https://github.com/basher83/Zammad-MCP/pull/329) | `329e6048` / `329e60480901` | Request-changes verdict as issue comment at 329e604: README conflict; own additions correct. Existing review also flags missing rate-limited bot signal.[41] | CONFLICTING / (blank) | {'pass': 7} |
| [#307](https://github.com/basher83/Zammad-MCP/pull/307) | `f9d98358` / `57d014ff4b58` | Formal CHANGES_REQUESTED at 57d014f for TicketUpdate quote handling; later f9d9835 author-side fix plus CodeRabbit no-actionable re-review at new head; no later maintainer-account verdict.[20] | MERGEABLE / CHANGES_REQUESTED | {'fail': 1, 'pass': 3} |
| [#324](https://github.com/basher83/Zammad-MCP/pull/324) | `d94d0b7e` / `d94d0b7e885d` | Request-changes verdict published as issue comment at d94d0b7; own tests deemed correct, inherited #307 defect/sequencing blocked.[36] | MERGEABLE / (blank) | {'fail': 2, 'pass': 15} |
| [#314](https://github.com/basher83/Zammad-MCP/pull/314) | `106ab7b2` / `106ab7b222a3` | CHANGES_REQUESTED; no later fix or re-review in archive.[26] | MERGEABLE / CHANGES_REQUESTED | {'pass': 4} |
| [#333](https://github.com/basher83/Zammad-MCP/pull/333) | `1064ad40` / `1064ad403fa6` | Approve at 1064ad4 via owner issue comment, not formal approval.[45] | MERGEABLE / (blank) | {'pass': 16, 'fail': 1} |
| [#340](https://github.com/basher83/Zammad-MCP/pull/340) | `0357fae8` / `0357fae86152` | Approve via owner issue comment at 0357fae; no requested changes.[52] | MERGEABLE / (blank) | {'pass': 4} |
| [#343](https://github.com/basher83/Zammad-MCP/pull/343) | `2c422392` / `2c4223925ce1` | Approve via owner issue comment at 2c42239; no requested changes.[55] | MERGEABLE / (blank) | {'pass': 4} |
| [#335](https://github.com/basher83/Zammad-MCP/pull/335) | `c5b6f0f4` / `c5b6f0f49ce1` | Approve at c5b6f0f in COMMENTED review, not formal APPROVED state; no blocking findings.[47] | MERGEABLE / (blank) | {'fail': 2, 'pass': 16} |
| [#336](https://github.com/basher83/Zammad-MCP/pull/336) | `808f7ba3` / `808f7ba31b29` | Approve on 808f7ba in two re-review comments; NOT a submitted GitHub APPROVED review (self-approval rejected).[48] | MERGEABLE / (blank) | {'fail': 2, 'pass': 16} |
| [#312](https://github.com/basher83/Zammad-MCP/pull/312) | `3d28c0fc` / `1d543d568137` | CHANGES_REQUESTED on 1d543d56; head 3d28c0f adds destructive annotation; no subsequent maintainer re-review.[24] | MERGEABLE / CHANGES_REQUESTED | {'pass': 4} |
| [#334](https://github.com/basher83/Zammad-MCP/pull/334) | `a9910a3e` / `a9910a3e2db0` | Approve verdict in issue comment at a9910a3; formal approval not evidenced (comment itself says no submitted reviews).[46] | MERGEABLE / (blank) | {'pass': 16, 'fail': 1} |
| [#339](https://github.com/basher83/Zammad-MCP/pull/339) | `c5b42569` / `c5b425694f82` | Approve via owner issue comment at c5b4256; no requested changes.[51] | MERGEABLE / (blank) | {'pass': 4} |
| [#315](https://github.com/basher83/Zammad-MCP/pull/315) | `69d3cfd2` / `69d3cfd285b7` | APPROVED formal review; head unchanged.[27] | MERGEABLE / (blank) | {'fail': 1, 'pass': 3} |
| [#331](https://github.com/basher83/Zammad-MCP/pull/331) | `13222f4f` / `13222f4f028d` | Approve in maintainer comment; not formal APPROVED review.[43] | MERGEABLE / (blank) | {'fail': 2, 'pass': 15} |
| [#316](https://github.com/basher83/Zammad-MCP/pull/316) | `743b0ae5` / `743b0ae57742` | CHANGES_REQUESTED; no later fix or re-review.[28] | MERGEABLE / CHANGES_REQUESTED | {'fail': 1, 'pass': 3} |
| [#338](https://github.com/basher83/Zammad-MCP/pull/338) | `65313d4f` / `65313d4f975b` | Latest approve re-review at 65313d4 (05:47:45Z), superseding request-changes passes on 10e6a29/27490a2; issue comments, not formal approval.[50] | MERGEABLE / (blank) | {'fail': 2, 'pass': 16} |
| [#341](https://github.com/basher83/Zammad-MCP/pull/341) | `e5a0e7a4` / `8370c0c61f22` | Last published verdict request changes at 8370c0c; author reports both fixes in current e5a0e7a; no later re-reviewed approve verdict.[53] | MERGEABLE / (blank) | {'fail': 2, 'pass': 15} |
| [#337](https://github.com/basher83/Zammad-MCP/pull/337) | `6cbc840f` / `6cbc840fd34d` | Request changes at 6cbc840 in COMMENTED review; head unchanged, blocker not fixed.[49] | MERGEABLE / (blank) | {'pass': 15, 'fail': 2} |
| [#267](https://github.com/basher83/Zammad-MCP/pull/267) | `2b7d13a0` / `81dbf6e2ce52` | Formal CHANGES_REQUESTED on 81dbf6e; head 2b7d13a is its direct child with review-response changes. No maintainer re-review on new head.[13] | MERGEABLE / CHANGES_REQUESTED | {'fail': 1, 'pass': 3} |
| [#344](https://github.com/basher83/Zammad-MCP/pull/344) | `06b3ec10` / `not pinned` | No maintainer verdict. CodeRabbit rate-limited without review; Codacy reports 46 minor documentation issues.[56] | MERGEABLE / (blank) | {'fail': 2, 'pass': 15} |
| [#200](https://github.com/basher83/Zammad-MCP/pull/200) | `64324d8f` / `64324d8fff64` | Maintainer parked on 2026-04-30; formal CHANGES_REQUESTED on current head 64324d8 on 2026-09-07.[7] | CONFLICTING / CHANGES_REQUESTED | {'pass': 3} |
| [#264](https://github.com/basher83/Zammad-MCP/pull/264) | `d7fd3466` / `d7fd3466707f` | Formal CHANGES_REQUESTED on current d7fd346; recommends closing as superseded by 5dc76d3.[12] | CONFLICTING / CHANGES_REQUESTED | {'pass': 8, 'skipping': 1} |
| [#317](https://github.com/basher83/Zammad-MCP/pull/317) | `a97daf50` / `a97daf5093d2` | Formal CHANGES_REQUESTED on current a97daf5; close as superseded by c0bc500 / #259.[29] | CONFLICTING / CHANGES_REQUESTED | {'pass': 4} |

## Interpretation

Conflicts are current GitHub observations, not inferred from filenames. Historical fork-workflow authorization notes remain historical unless separately revalidated. Codacy ACTION_REQUIRED is not equivalent to test failure; its literal state and check URL are retained in JSON. Historical security-audit failures on other PR heads must not be presented as the state of current main or as unresolved findings on #342.

PR #332’s approval comment does not pin a reviewed SHA, so exact-head coverage is intentionally uncertain. #276’s approval was formally dismissed. #335 approve and #337 request-changes are textual verdicts in COMMENTED submitted reviews. Owner-authored issue-comment verdicts on other PRs remain technical evidence, not formal approvals.[44][14][47]

## Sources

[7] https://github.com/basher83/Zammad-MCP/pull/200
[12] https://github.com/basher83/Zammad-MCP/pull/264
[13] https://github.com/basher83/Zammad-MCP/pull/267
[14] https://github.com/basher83/Zammad-MCP/pull/276
[16] https://github.com/basher83/Zammad-MCP/pull/287
[18] https://github.com/basher83/Zammad-MCP/pull/291
[19] https://github.com/basher83/Zammad-MCP/pull/306
[20] https://github.com/basher83/Zammad-MCP/pull/307
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
