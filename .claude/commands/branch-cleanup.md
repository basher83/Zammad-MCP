---
allowed-tools: Bash(git branch:*), Bash(git for-each-ref:*), Bash(git log:*), Bash(git status:*), Bash(git fetch:*), Bash(git remote prune:*), Bash(gh pr list:*), Read
argument-hint: [--dry-run] | [--force] | [--local-only] | [--remote-only]
description: Clean up merged local branches and stale remote-tracking references
model: sonnet
---

# Branch Cleanup

Clean up merged branches: $ARGUMENTS

## Current state

- Current branch: !`git branch --show-current`
- Local branches merged into main: !`git branch --merged main`
- Recent local branches: !`git for-each-ref --count=15 --sort=-committerdate refs/heads/ --format='%(refname:short) %(objectname:short) %(committerdate:relative)'`
- Remote-tracking branches: !`git branch -r`

## Rules

- Never delete `main`, the current branch, or a branch with commits that are on no merged PR and not on `main`.
- `git branch --merged` does not show squash-merged branches. Treat a branch as merged when `gh pr list --head <branch> --state merged` returns its PR.
- Delete merged local branches with `git branch -d`. Use `git branch -D` only for a squash-merged branch whose PR is merged.
- Before you delete a branch, print its name and tip SHA. The user can restore it with `git branch <name> <sha>`.
- `git remote prune origin` removes stale remote-tracking references. It changes only the local repository.
- Deleting a branch on the remote (`git push origin --delete <branch>`) needs explicit user confirmation for each branch, in every mode.

## Modes

- Default: list the candidates, ask before each local deletion, then report what changed.
- `--dry-run`: list the candidates and the commands you would run. Change nothing.
- `--force`: delete merged local branches without asking. Remote deletions still need confirmation.
- `--local-only`: act only on local branches.
- `--remote-only`: prune remote-tracking references and propose remote deletions.
