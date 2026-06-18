# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function eachdir --description "Run a (simple) command in each immediate subdirectory"
    if test -z "$argv[1]"
        echo "usage: eachdir <command...>" >&2
        return 2
    end

    # NUL-delimited (-print0 / sort -z / split0) so paths with spaces or
    # newlines survive intact instead of being split into bogus iterations.
    for dir in (find . -mindepth 1 -maxdepth 1 -type d -print0 | sort -z | string split0)
        echo "── "(string replace -r '^\./' '' -- $dir)" ──"
        pushd $dir >/dev/null; or continue
        $argv
        # If $argv touched the dir stack, a bare popd could resume from the wrong
        # directory; bail out rather than iterate from an unknown CWD.
        popd >/dev/null; or break
    end
end
