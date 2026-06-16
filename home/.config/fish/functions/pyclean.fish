# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function pyclean --description "Recursively remove Python caches (__pycache__, .pytest_cache, .mypy_cache, .ruff_cache, *.pyc)"
    set -l dirs __pycache__ .pytest_cache .mypy_cache .ruff_cache

    if contains -- -n $argv; or contains -- --dry-run $argv
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
