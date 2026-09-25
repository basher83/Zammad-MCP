# Preserve Content During Documentation Changes

Use this reference for content rewrites, moves, splits, or deletions. Skip mapping for spelling-only edits.
Apply it within the requested scope. Preserve meaning, conditions, and reader access while improving structure.

## Capture the source

Before editing, identify each source unit: a claim, warning, procedure, example, table, contract, or troubleshooting fact.
Record its file, heading, and line range against the source revision.
For uncommitted source content, identify the working-copy baseline instead of attributing it to HEAD.
Keep enough source text to compare meaning after editing. Retain a snapshot when resumption requires it.

Dense sections need separate rows for distinct claims and safety conditions.
A single row saying "configuration covered" cannot account for authentication options, defaults, and TLS warnings.

## Map every unit

Use these fields in an inline table or the task's existing evidence artifact:

| Field | Required content |
|---|---|
| Source | Revision or baseline, file, section, and line range |
| Unit | The specific claim, warning, example, or procedure |
| Decision | `keep`, `move`, or `drop` |
| Destination | Final file and section/anchor for retained content |
| Evidence | Meaning comparison, or evidence and reason for deletion |
| Status | `checked` or `unresolved`, with the remaining gap |

Use `keep` when the unit stays in its page, including a meaning-preserving rewrite.
Use `move` when the unit changes pages. Both decisions require a checked destination.
Use `drop` only with a reason: obsolete, unsupported, or duplicated at a named destination.
Do not silently remove an uncertain claim. Mark it unresolved until evidence supports a decision.
For an authorized factual correction, record the old claim, replacement, and supporting evidence.

For example, a README split needs separate units for each authentication option and the TLS warning.
Map each unit to its actual destination heading. Then check its conditions and qualifiers against the source.
Do not populate destinations from a planned outline without reading the final pages.

## Check the result

1. Account for every source unit. Compare retained facts, numbers, defaults, qualifiers, and warnings with the final text.
1. Check complete examples, including setup, authentication, expected results, and cleanup where applicable.
1. Check old paths and fragments separately. A path redirect does not prove that a fragment still reaches its content.
1. Use the repository's rendering rules and supported anchor syntax. Report compatibility gaps that require a separate decision.
1. Check inbound links and the reader's route from the entry page to the moved instructions.
1. Report unresolved rows. Do not claim full preservation while rows or destinations remain unchecked.

Lint and link checks supplement this comparison. They cannot establish semantic preservation.
An inventory alone is not a preservation map.
If a structured artifact uses `mappings[]`, require actual populated source-to-destination records.
The array's existence or length alone does not prove coverage.

## Keep evidence proportional

Keep a small map in chat or the handoff. Do not create a ledger for every rewrite.
For large or resumable work, follow [Evidence and artifacts](../SKILL.md#evidence-and-artifacts).
State the artifact's consumer and purpose, then reuse the task's evidence location.
Preservation accounting does not authorize editing, publishing, or expanding the requested scope.
