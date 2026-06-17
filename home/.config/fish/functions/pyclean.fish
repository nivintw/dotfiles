# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function pyclean --description "Recursively remove Python caches (__pycache__, .pytest_cache, .mypy_cache, .ruff_cache, *.pyc)"
    # Parse flags strictly: an unknown flag (e.g. a mistyped --dryrun) makes
    # argparse fail rather than silently falling through to the destructive path.
    argparse h/help n/dry-run -- $argv
    or return 2

    if set -q _flag_help
        echo "Usage: pyclean [-n|--dry-run] [-h|--help]"
        echo
        echo "Recursively remove Python caches (__pycache__, .pytest_cache,"
        echo ".mypy_cache, .ruff_cache, *.pyc) from the current directory down."
        echo
        echo "Options:"
        echo "  -n, --dry-run   List what would be removed without deleting anything."
        echo "  -h, --help      Show this help and exit."
        return 0
    end

    # No positional arguments are expected; reject stray input rather than delete.
    if set -q argv[1]
        echo "pyclean: unexpected argument '$argv[1]' (see pyclean --help)" >&2
        return 2
    end

    set -l dirs __pycache__ .pytest_cache .mypy_cache .ruff_cache

    if set -q _flag_dry_run
        echo "(dry run: nothing will be deleted)"
        for d in $dirs
            find . -type d -name $d -prune
        end
        find . -type f -name '*.pyc'
        return 0
    end

    for d in $dirs
        find . -type d -name $d -prune -exec rm -rf {} +
    end
    find . -type f -name '*.pyc' -delete
    echo "Python caches cleaned."
end
