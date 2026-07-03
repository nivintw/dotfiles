# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

complete -c ollm -s r -l role -x -a "fast bulk brainstorm vision" -d "Model role to use"
complete -c ollm -s m -l model -x -d "Explicit model tag (overrides --role)"
complete -c ollm -l think -d "Enable thinking (models that support it)"
complete -c ollm -s n -l num-predict -x -d "Max tokens to generate (default 4096)"
complete -c ollm -s i -l image -r -d "Attach an image (vision models)"
complete -c ollm -s t -l timeout -x -d "Request timeout in seconds (default 300)"
complete -c ollm -s l -l list -d "Show roles, resolved tags, and installed state"
complete -c ollm -s h -l help -d "Show help and exit"
