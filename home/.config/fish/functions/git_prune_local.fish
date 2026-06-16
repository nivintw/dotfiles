# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function git_prune_local --description "Delete local branches that have been merged into main"
    argparse h/help n/dry-run -- $argv
    or return 1

    if set -q _flag_help
        echo "Usage: git_prune_local [-n|--dry-run] [-h|--help]"
        echo
        echo "Delete local branches that have been merged into the default branch."
        echo "Run from inside a git repository (assumes the remote is named 'origin')."
        echo
        echo "A branch is deleted when its commits are verified present in the default"
        echo "branch -- via a normal/rebase merge, or a squash merge (detected by patch"
        echo "id). A branch whose remote is gone but whose commits are NOT in the default"
        echo "branch is kept, so an accidentally-deleted remote can't cost you your only"
        echo "local copy. Local-only branches merged into the default branch are deleted;"
        echo "branches still tracking a live remote are left alone."
        echo
        echo "Options:"
        echo "  -n, --dry-run   Show what would be deleted without deleting anything."
        echo "  -h, --help      Show this help and exit."
        return 0
    end

    # Ensure we're in a git repository
    if not git rev-parse --git-dir >/dev/null 2>&1
        echo "Error: Not a git repository."
        return 1
    end

    if set -q _flag_dry_run
        echo "(dry run: no branches will be deleted)"
    end

    # Fetch the latest changes from the remote
    echo "Fetching latest changes from remote..."
    git fetch --prune

    # NOTE: assumes the remote is named "origin".
    # Determine the default branch on the remote (usually origin/main).
    set default_branch (git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|^refs/remotes/||')
    if test -z "$default_branch"
        set default_branch origin/main # Fallback to origin/main if HEAD is not set
    end
    set default_local (string replace 'origin/' '' -- $default_branch)

    # Don't touch the branch we're currently on (empty if HEAD is detached).
    set current_branch (git symbolic-ref --short -q HEAD)

    # Branches whose remote-tracking branch is gone (PR was merged and deleted).
    # for-each-ref avoids parsing the porcelain `git branch -vv` output, so there
    # are no `*`/`+` decorations to strip and branch names with slashes are safe.
    set gone_branches (git for-each-ref --format '%(refname:short) %(upstream:track)' refs/heads \
        | string replace -rf '^(\S+) \[gone\]$' '$1')

    # Branches that are direct ancestors of the default branch (traditional merge).
    set merged_branches (git branch --merged $default_branch | grep -v '^[*+]' | string trim | string match -v -- $default_local)

    set deleted_count 0
    set skipped_count 0
    set kept_count 0
    set had_failure 0

    for branch in $gone_branches
        test "$branch" = "$current_branch"; and continue

        # Per-commit patch-id check: are all of the branch's commits already in the
        # default branch? Empty result => normal or rebase merge (handled silently).
        set unmerged (git log --cherry-pick --right-only --oneline $default_branch...$branch 2>/dev/null)

        set reason
        if test -z "$unmerged"
            set reason merged
        else
            # Not patch-equivalent per commit. Either a squash merge (collapsed to a
            # single commit on the default branch with a new patch-id) or a remote
            # deleted without merging. Collapse the branch to one synthetic commit of
            # its total diff against the merge-base, then ask whether the default
            # branch already contains that patch (`git cherry` prints "-" if so).
            set mb (git merge-base $default_branch $branch 2>/dev/null)
            set synth
            if test -n "$mb"
                set synth (git commit-tree "$branch^{tree}" -p $mb -m squash-check 2>/dev/null)
            end

            if test -n "$synth"; and string match -q -- '-*' (git cherry $default_branch $synth 2>/dev/null)
                set reason squash-merged
            else
                # Genuinely not in the default branch. Could be a remote that was
                # deleted without merging, so keep it rather than risk discarding
                # the only remaining copy. Verify and delete by hand if intended.
                echo "Skipping branch (commits not in $default_local): $branch"
                echo "  Unmerged commits:"
                printf '    %s\n' $unmerged
                set skipped_count (math $skipped_count + 1)
                continue
            end
        end

        # reason is "merged" or "squash-merged": commits are verified present in the
        # default branch, so force-delete is safe even when -d would refuse.
        if set -q _flag_dry_run
            echo "[dry-run] Would delete $reason branch: $branch"
            set deleted_count (math $deleted_count + 1)
        else
            echo "Deleting $reason branch: $branch"
            if git branch -D $branch
                set deleted_count (math $deleted_count + 1)
            else
                echo "    WARNING: Failed to delete branch: $branch"
                set had_failure 1
            end
        end
    end

    # Also delete branches that are local-only (no upstream remote).
    # Branches still tracking a live remote are left alone.
    # gone-remote branches were already handled above.
    for branch in $merged_branches
        if not contains -- $branch $gone_branches
            set upstream (git config --get branch.$branch.remote 2>/dev/null)
            if test -z "$upstream"
                # No upstream, but merged into the default branch. Safe to delete.
                if set -q _flag_dry_run
                    echo "[dry-run] Would delete merged local-only branch: $branch"
                    set deleted_count (math $deleted_count + 1)
                else
                    echo "Deleting merged local-only branch: $branch"
                    if git branch -d $branch
                        set deleted_count (math $deleted_count + 1)
                    else
                        echo "    WARNING: Failed to delete branch: $branch"
                        set had_failure 1
                    end
                end
            else
                # Has an upstream remote that still exists, but is merged. Leave it alone.
                echo "Skipping branch (has live upstream): $branch"
                set kept_count (math $kept_count + 1)
            end
        end
    end

    if test $deleted_count -eq 0 -a $skipped_count -eq 0 -a $kept_count -eq 0
        echo "No local branches to prune."
    else
        echo "Pruning complete: Deleted $deleted_count branch(es), Skipped $skipped_count branch(es) (need review), Kept $kept_count branch(es) with live upstreams."
    end

    # Non-zero exit only if a delete we attempted actually failed.
    test $had_failure -eq 0
end
