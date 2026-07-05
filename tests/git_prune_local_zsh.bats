#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Tests for the git_prune_local zsh function — the zsh twin of
# tests/git_prune_local.bats, exercising the same branch-state matrix: this is the
# one piece of real logic in the zsh port, where a bug would delete branches that
# aren't actually merged.
#
# Strategy: identical to the fish suite — each test builds a throwaway git repo with
# a LOCAL bare "origin" so the function's `git fetch --prune` and origin/HEAD lookups
# behave for real, stages a known branch state, then runs `git_prune_local --dry-run`
# and asserts which branches it would (or would not) delete.
#
# Run:  bats tests/git_prune_local_zsh.bats

setup() {
  TMP="$(mktemp -d)"
  ORIGIN="$TMP/origin.git"
  WORK="$TMP/work"

  git init -q --bare -b main "$ORIGIN"
  git init -q --template= -b main "$WORK"
  cd "$WORK" || return 1
  git config user.email tester@example.test
  git config user.name tester
  git config commit.gpgsign false

  git commit -q --allow-empty -m init
  git remote add origin "$ORIGIN"
  git push -q -u origin main
  git remote set-head origin -a # populate refs/remotes/origin/HEAD -> main

  FUNC="$BATS_TEST_DIRNAME/../home/.config/zsh/functions/git_prune_local"
}

teardown() {
  rm -rf "$TMP"
}

prune() {
  run zsh -c "source '$FUNC'; git_prune_local --dry-run"
}

@test "zsh: merged + gone-remote branch is deleted" {
  git checkout -q -b feature
  git commit -q --allow-empty -m "feature work"
  git push -q -u origin feature
  git checkout -q main
  git merge -q --no-ff feature -m "merge feature"
  git push -q origin main
  git push -q origin --delete feature # remote gone -> local marked [gone]

  prune
  [ "$status" -eq 0 ]
  [[ "$output" == *"Would delete merged branch: feature"* ]]
}

@test "zsh: multi-commit squash-merged + gone-remote branch is detected and deleted" {
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

@test "zsh: gone-remote but UNMERGED branch is kept (not deleted)" {
  git checkout -q -b orphan
  git commit -q --allow-empty -m "orphan work (never merged)"
  git push -q -u origin orphan
  git checkout -q main
  git push -q origin --delete orphan # remote deleted WITHOUT merging

  prune
  [ "$status" -eq 0 ]
  [[ "$output" == *"Skipping branch (commits not in main): orphan"* ]]
  [[ "$output" != *"Would delete"*"orphan"* ]]
}

@test "zsh: merged local-only branch (no upstream) is deleted" {
  git checkout -q -b locmerged
  git commit -q --allow-empty -m "locmerged work"
  git checkout -q main
  git merge -q --no-ff locmerged -m "merge locmerged"
  git push -q origin main

  prune
  [ "$status" -eq 0 ]
  [[ "$output" == *"Would delete merged local-only branch: locmerged"* ]]
}

@test "zsh: unmerged local-only branch is left alone" {
  git checkout -q -b locunmerged
  git commit -q --allow-empty -m "locunmerged work"
  git checkout -q main

  prune
  [ "$status" -eq 0 ]
  [[ "$output" != *"locunmerged"* ]]
}

@test "zsh: the current branch is never deleted, even when merged + gone" {
  git checkout -q -b cur
  git commit -q --allow-empty -m "cur work"
  git push -q -u origin cur
  git checkout -q main
  git merge -q --no-ff cur -m "merge cur"
  git push -q origin main
  git push -q origin --delete cur
  git checkout -q cur # stay on the merged+gone branch

  prune
  [ "$status" -eq 0 ]
  [[ "$output" != *"Would delete"*"cur"* ]]
}

@test "zsh: a branch still tracking a live remote is kept" {
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

# The dry-run tests above cover the decision; this one exercises the real delete
# path — that a merged+gone branch is actually removed, twice in a row, so the
# second-iteration stray-output bug (a bare `local` re-declared on an already-local
# var prints to stdout in zsh) can't hide behind a single-branch happy path.
@test "zsh: two merged + gone-remote branches are both actually deleted (real run)" {
  git checkout -q -b feature1
  git commit -q --allow-empty -m "feature1 work"
  git push -q -u origin feature1
  git checkout -q main
  git merge -q --no-ff feature1 -m "merge feature1"
  git push -q origin main
  git push -q origin --delete feature1

  git checkout -q -b feature2
  git commit -q --allow-empty -m "feature2 work"
  git push -q -u origin feature2
  git checkout -q main
  git merge -q --no-ff feature2 -m "merge feature2"
  git push -q origin main
  git push -q origin --delete feature2

  run zsh -c "source '$FUNC'; git_prune_local"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Deleting merged branch: feature1"* ]]
  [[ "$output" == *"Deleting merged branch: feature2"* ]]
  # No stray "name=value" lines from a re-declared bare `local` inside the loop.
  [[ "$output" != *$'\n'"unmerged="* ]]
  run git branch --list feature1 feature2
  [ -z "$output" ] # both branches are really gone
}
