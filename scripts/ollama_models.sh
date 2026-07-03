# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Canonical Ollama model identifiers — pure data, no logic, no side effects on source.
# Shared by the installer (which provisions these), uninstall.sh (which offers to remove
# them), and the stowed `ollm` offload helper (which resolves --role from them) so the
# consumers can never drift: change a model tag here and all follow.
#
#   OLLAMA_MODEL            — fast tier; backs GitLens and is the non-MLX fallback (~2.5GB)
#   OLLAMA_VISION_MODEL     — lightweight vision: screenshot/diagram triage, GGUF (~3.3GB)
#   OLLAMA_MLX_MODEL        — gated MLX coding model for Claude bulk-offload (~21GB)
#   OLLAMA_BRAINSTORM_MODEL — gated generalist (GGUF, rides the same big-memory gate):
#                             brainstorm/summarize/analysis (~17GB)
#
# Manual companions when OLLAMA_MODEL changes: gitlens.ai.model in the stowed VS Code
# settings, and the pinned fast tag in tests/ollm.bats.
#
# shellcheck disable=SC2034  # consumed by the installer / uninstall.sh / ollm that source this
OLLAMA_MODEL="qwen3:4b-instruct-2507-q4_K_M"
OLLAMA_VISION_MODEL="qwen3-vl:4b-instruct"
OLLAMA_MLX_MODEL="qwen3.5:35b-a3b-coding-nvfp4"
OLLAMA_BRAINSTORM_MODEL="gemma4:26b"

# Tags this repo once provisioned but no longer uses (space-separated). The installer
# ignores them; uninstall.sh offers their removal so upgraded machines reclaim the disk.
OLLAMA_LEGACY_MODELS="qwen2.5-coder:7b"
