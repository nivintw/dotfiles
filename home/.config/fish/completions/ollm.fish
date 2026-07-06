# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

complete -c ollm -s r -l role -x -a "fast bulk brainstorm vision" -d "Model role to use"
complete -c ollm -s m -l model -x -d "Explicit model tag (overrides --role)"
complete -c ollm -l think -d "Enable thinking (models that support it)"
complete -c ollm -s n -l num-predict -x -d "Max tokens to generate (default 4096)"
complete -c ollm -s i -l image -r -d "Attach an image (vision models)"
complete -c ollm -s t -l timeout -x -d "Generation timeout in seconds (default 300)"
complete -c ollm -l no-input -d "Never read stdin"
complete -c ollm -s l -l list -d "Show roles, resolved tags, and installed state"
complete -c ollm -s h -l help -d "Show help and exit"
complete -c ollm -l tools -d "Sandboxed read-only tool-calling loop (read_file/grep/ls)"
complete -c ollm -l tools-root -r -d "Sandbox root for --tools (default: cwd)"
complete -c ollm -l tools-cap -x -d "Max --tools round-trips (default: 6)"
