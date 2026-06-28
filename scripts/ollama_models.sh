# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Canonical Ollama model identifiers — pure data, no logic, no side effects on source.
# Shared by install.sh (which provisions these) and uninstall.sh (which offers to remove
# them) so the two can never drift: change a model tag here and both follow.
#
#   OLLAMA_MODEL     — baseline; backs GitLens and is the non-MLX fallback (~4.7GB)
#   OLLAMA_MLX_MODEL — gated MLX reasoning model for Claude bulk-offload (~21GB)
#
# shellcheck disable=SC2034  # consumed by the install.sh / uninstall.sh that source this
OLLAMA_MODEL="qwen2.5-coder:7b"
OLLAMA_MLX_MODEL="qwen3.5:35b-a3b-coding-nvfp4"
