# Task cards

Every implementation step is a card `docs/tasks/M<milestone>/T<m>.<n>-<slug>.md`. Opus writes the cards and the
contract headers they reference, and Haiku agents implement them. A card is the agent's whole mandate; anything it does
not list is out of scope (see `CLAUDE.md` rule 1).

## Card template

```
# Tx.y — <title>
Milestone: Mx · Depends on: <ids> · Parallel-safe: yes|no
## Goal            one paragraph: what exists after this card that did not before
## Read first      files / SPEC sections / upstream URLs (pinned revisions)
## Create          exact paths
## Modify          exact paths (and what to change)
## Do not touch    anything notable beyond CLAUDE.md rule 1
## Interface       verbatim signatures / CLI / file formats that other cards rely on
## Steps           ordered, concrete
## Acceptance      commands that must pass, with expected observable results
## Commit          `Tx.y: <title>`
```

## Execution protocol (per milestone)

1. Opus writes the cards (and any `CONTRACT:` headers) and commits them.
2. A Workflow runs the cards in dependency order on Haiku. Each card runs its acceptance commands and makes one commit.
3. A gate agent re-runs the acceptance commands on a clean checkout of the commit. On failure, the card is retried once
   with the failure log; a second failure escalates to Opus.
4. Every 12th card slot is an Opus code-quality audit (`TQ.n`).
5. Opus reviews each milestone: spec conformance, naming, structure, and whether to reorganize. Its findings become
   fix-up cards. Then the branch is pushed.
