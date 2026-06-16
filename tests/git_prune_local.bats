#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Tests for the git_prune_local fish function — the one piece of real logic in
# this repo, where a bug would delete branches that aren't actually merged.
#
# Strategy: each test builds a throwaway git repo with a LOCAL bare "origin" so
# the function's `git fetch --prune` and origin/HEAD lookups behave for real,
# stages a known branch state, then runs `git_prune_local --dry-run` and asserts
# which branches it would (or would not) delete. --dry-run keeps it non-destructive
# — we test the decision, not the `git branch -D`.
#
# Run:  bats tests/git_prune_local.bats

setup() {
  TMP="$(mktemp -d)"
  ORIGIN="$TMP/origin.git"
  WORK="$TMP/work"

  git init -q --bare "$ORIGIN"
  # --template= skips the user's init.templateDir (prek hook shims) for speed and
  # isolation; commit.gpgsign off so tests don't hit the 1Password SSH signer.
  git init -q --template= -b main "$WORK"
  cd "$WORK" || return 1
  git config user.email tester@example.test
  git config user.name tester
  git config commit.gpgsign false

  git commit -q --allow-empty -m init
  git remote add origin "$ORIGIN"
  git push -q -u origin main
  git remote set-head origin -a   # populate refs/remotes/origin/HEAD -> main

  FUNC="$BATS_TEST_DIRNAME/../home/.config/fish/functions/git_prune_local.fish"
}

teardown() {
  rm -rf "$TMP"
}

prune() {
  run fish -c "source '$FUNC'; git_prune_local --dry-run"
}

@test "merged + gone-remote branch is deleted" {
  git checkout -q -b feature
  git commit -q --allow-empty -m "feature work"
  git push -q -u origin feature
  git checkout -q main
  git merge -q --no-ff feature -m "merge feature"
  git push -q origin main
  git push -q origin --delete feature   # remote gone -> local marked [gone]

  prune
  [ "$status" -eq 0 ]
  [[ "$output" == *"Would delete merged branch: feature"* ]]
}

@test "multi-commit squash-merged + gone-remote branch is detected and deleted" {
  # A multi-commit branch collapsed into ONE commit on main is the case the
  # function's synthetic commit-tree path exists for: per-commit patch-id
  # matching can't see it (no individual commit is patch-equivalent on main), so
  # it must reconstruct the branch's whole diff and ask if that patch landed.
  git checkout -q -b sq
  echo a > sq.txt && git add sq.txt && git commit -q -m "sq part 1"
  echo b >> sq.txt && git add sq.txt && git commit -q -m "sq part 2"
  git push -q -u origin sq
  git checkout -q main
  git merge -q --squash sq
  git commit -q -m "squash sq"
  git push -q origin main
  git push -q origin --delete sq

  prune
  [ "$status" -eq 0 ]
  [[ "$output" == *"Would delete squash-merged branch: sq"* ]]
}

@test "gone-remote but UNMERGED branch is kept (not deleted)" {
  git checkout -q -b orphan
  git commit -q --allow-empty -m "orphan work (never merged)"
  git push -q -u origin orphan
  git checkout -q main
  git push -q origin --delete orphan   # remote deleted WITHOUT merging

  prune
  [ "$status" -eq 0 ]
  [[ "$output" == *"Skipping branch (commits not in main): orphan"* ]]
  [[ "$output" != *"Would delete"*"orphan"* ]]
}

@test "merged local-only branch (no upstream) is deleted" {
  git checkout -q -b locmerged
  git commit -q --allow-empty -m "locmerged work"
  git checkout -q main
  git merge -q --no-ff locmerged -m "merge locmerged"
  git push -q origin main

  prune
  [ "$status" -eq 0 ]
  [[ "$output" == *"Would delete merged local-only branch: locmerged"* ]]
}

@test "unmerged local-only branch is left alone" {
  git checkout -q -b locunmerged
  git commit -q --allow-empty -m "locunmerged work"
  git checkout -q main

  prune
  [ "$status" -eq 0 ]
  [[ "$output" != *"locunmerged"* ]]
}

@test "the current branch is never deleted, even when merged + gone" {
  git checkout -q -b cur
  git commit -q --allow-empty -m "cur work"
  git push -q -u origin cur
  git checkout -q main
  git merge -q --no-ff cur -m "merge cur"
  git push -q origin main
  git push -q origin --delete cur
  git checkout -q cur   # stay on the merged+gone branch

  prune
  [ "$status" -eq 0 ]
  [[ "$output" != *"Would delete"*"cur"* ]]
}

@test "a branch still tracking a live remote is kept" {
  git checkout -q -b live
  git commit -q --allow-empty -m "live work"
  git push -q -u origin live
  git checkout -q main
  git merge -q --no-ff live -m "merge live"
  git push -q origin main
  # remote branch NOT deleted -> still tracking a live upstream

  prune
  [ "$status" -eq 0 ]
  [[ "$output" == *"Skipping branch (has live upstream): live"* ]]
  [[ "$output" != *"Would delete"*"live"* ]]
}
