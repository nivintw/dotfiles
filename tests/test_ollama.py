# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phase 14: the Ollama model installer.

Covers install_ollama_models plus its helpers: the ollama-absent skip, the server-up
fast path and the launch/retry/detached-serve fallback, the model inventory parse, the
pull-skip vs pull-success vs pull-failure branches, and the MLX gate (arch / memory /
macOS-version) both ways. Four role models are covered: the two ungated models
(fast + vision), pulled on every capable machine, and the two MLX-gated models
(coding + brainstorm), pulled only when the MLX gate passes.

All subprocess goes through the ``commands`` seam; tests monkeypatch commands.run,
commands.run_ok, commands.which, and commands.read_text_or_empty at that boundary, and
patch subprocess.Popen for the one detached ``ollama serve`` call.
"""

from __future__ import annotations

import io
import subprocess

import pytest
from rich.console import Console

from dotfiles_install import commands, ollama
from dotfiles_install.context import InstallContext
from dotfiles_install.os_detect import OS
from dotfiles_install.ui import UI

_MODELS_FRAGMENT = (
    'OLLAMA_MODEL="qwen3:4b-instruct-2507-q4_K_M"\n'
    'OLLAMA_VISION_MODEL="qwen3-vl:4b-instruct"\n'
    'OLLAMA_MLX_MODEL="qwen3.5:35b-a3b-coding-nvfp4"\n'
    'OLLAMA_BRAINSTORM_MODEL="gemma4:26b"\n'
)


def _ctx() -> tuple[InstallContext, io.StringIO]:
    """Build an install context over a wide in-memory console (wide so lines don't wrap)."""
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    return InstallContext(ui=ui), out


def _completed(
    argv: list[str],
    returncode: int,
    stdout: str = "",
) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess like the commands seam returns."""
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="")


def _patch_model_ids(monkeypatch: pytest.MonkeyPatch, content: str = _MODELS_FRAGMENT) -> None:
    """Make _read_model_ids parse the given ollama_models.sh content."""
    monkeypatch.setattr(commands, "read_text_or_empty", lambda _path: content)


def _patch_server_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the first server probe succeed so _ensure_server_up is a no-op."""
    monkeypatch.setattr(ollama, "_server_responding", lambda: True)


def _patch_mlx(monkeypatch: pytest.MonkeyPatch, *, supported: bool) -> None:
    """Force the MLX gate result."""
    monkeypatch.setattr(ollama, "_mlx_supported", lambda: supported)


# --- _read_model_ids against the real fragment -----------------------------------------------


def test_read_model_ids_against_real_fragment() -> None:
    """Unmocked: parses the actual scripts/ollama_models.sh, pinning _MODEL_SPECS's var names.

    Every other test in this file monkeypatches commands.read_text_or_empty so the parser
    logic can be exercised against controlled fixtures; this one deliberately does not, so
    it also pins the OTHER half of the contract — that ollama._MODEL_SPECS still names the
    same four variables the real, checked-in fragment defines. A rename of either side alone
    (the fragment's vars or _MODEL_SPECS's tuple) would otherwise silently no-op this phase
    (or raise) without any test catching the drift.
    """
    models = ollama._read_model_ids()

    assert set(models) == {
        "OLLAMA_MODEL",
        "OLLAMA_VISION_MODEL",
        "OLLAMA_MLX_MODEL",
        "OLLAMA_BRAINSTORM_MODEL",
    }
    assert all(models.values()), f"expected every model id to be non-empty, got {models}"


# --- install_ollama_models: ollama absent -----------------------------------------------------


def test_ollama_absent_warns_and_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ollama isn't on PATH, a warn is emitted and nothing else runs."""
    monkeypatch.setattr(commands, "which", lambda _name: None)

    def _boom(*_a: object, **_k: object) -> object:
        msg = "should not run when ollama is absent"
        raise AssertionError(msg)

    monkeypatch.setattr(commands, "run", _boom)
    monkeypatch.setattr(commands, "run_ok", _boom)
    ctx, _ = _ctx()

    ollama.install_ollama_models(ctx)

    assert any("skipping Ollama setup" in w for w in ctx.ui.warnings)


# --- _read_model_ids --------------------------------------------------------------------------


def test_read_model_ids_parses_all_four(monkeypatch: pytest.MonkeyPatch) -> None:
    """All four ids are parsed, keyed by var name; no pattern swallows another's line."""
    _patch_model_ids(monkeypatch)

    models = ollama._read_model_ids()

    assert models == {
        "OLLAMA_MODEL": "qwen3:4b-instruct-2507-q4_K_M",
        "OLLAMA_VISION_MODEL": "qwen3-vl:4b-instruct",
        "OLLAMA_MLX_MODEL": "qwen3.5:35b-a3b-coding-nvfp4",
        "OLLAMA_BRAINSTORM_MODEL": "gemma4:26b",
    }


def test_read_model_ids_raises_on_unparsable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fragment missing the expected assignments raises (a broken-repo invariant)."""
    _patch_model_ids(monkeypatch, content="# nothing useful here\n")

    with pytest.raises(RuntimeError, match=r"ollama_models\.sh"):
        ollama._read_model_ids()


@pytest.mark.parametrize(
    "missing_var",
    ["OLLAMA_MODEL", "OLLAMA_VISION_MODEL", "OLLAMA_MLX_MODEL", "OLLAMA_BRAINSTORM_MODEL"],
)
def test_read_model_ids_raises_naming_missing_var(
    monkeypatch: pytest.MonkeyPatch, missing_var: str
) -> None:
    """When exactly one var is missing, the RuntimeError names that specific var."""
    lines = [
        line for line in _MODELS_FRAGMENT.splitlines() if not line.startswith(f'{missing_var}="')
    ]
    _patch_model_ids(monkeypatch, content="\n".join(lines) + "\n")

    with pytest.raises(RuntimeError, match=rf"could not parse {missing_var} from"):
        ollama._read_model_ids()


def test_install_degrades_to_warning_on_unparsable_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed models fragment warns and skips the phase — it must NOT abort the install."""
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/local/bin/ollama")
    _patch_model_ids(monkeypatch, content="# nothing useful here\n")
    ctx, out = _ctx()

    ollama.install_ollama_models(ctx)  # must not raise

    assert any("skipping Ollama setup" in w for w in ctx.ui.warnings)
    assert "ollama_models.sh" in out.getvalue()


# --- install_ollama_models: pull behavior (server already up) ---------------------------------


def test_ungated_pulled_when_absent_mlx_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty inventory, non-MLX machine → the two ungated models pull; both gated ones skip."""
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/local/bin/ollama")
    _patch_model_ids(monkeypatch)
    _patch_server_up(monkeypatch)
    _patch_mlx(monkeypatch, supported=False)

    run_calls: list[list[str]] = []
    run_ok_calls: list[list[str]] = []

    def _run(argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        run_calls.append(list(argv))
        # `ollama list` → header only (empty inventory).
        return _completed(argv, 0, stdout="NAME  ID  SIZE  MODIFIED\n")

    def _run_ok(argv: list[str], **_k: object) -> bool:
        run_ok_calls.append(list(argv))
        return True

    monkeypatch.setattr(commands, "run", _run)
    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, out = _ctx()

    ollama.install_ollama_models(ctx)

    assert ["ollama", "pull", "qwen3:4b-instruct-2507-q4_K_M"] in run_ok_calls
    assert ["ollama", "pull", "qwen3-vl:4b-instruct"] in run_ok_calls
    assert not any("qwen3.5" in c[-1] for c in run_ok_calls)  # MLX coding model not pulled
    assert not any("gemma4" in c[-1] for c in run_ok_calls)  # MLX brainstorm model not pulled
    assert "skipping large model qwen3.5:35b-a3b-coding-nvfp4" in out.getvalue()
    assert "skipping large model gemma4:26b" in out.getvalue()
    assert "Ollama model qwen3:4b-instruct-2507-q4_K_M pulled" in out.getvalue()
    assert "Ollama model qwen3-vl:4b-instruct pulled" in out.getvalue()


def test_baseline_already_present_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the fast-tier model is already in inventory, it's reported present and not pulled."""
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/local/bin/ollama")
    _patch_model_ids(monkeypatch)
    _patch_server_up(monkeypatch)
    _patch_mlx(monkeypatch, supported=False)

    inventory = (
        "NAME                            ID    SIZE\n"
        "qwen3:4b-instruct-2507-q4_K_M   abc   2.5GB\n"
        "qwen3-vl:4b-instruct            def   3.3GB\n"
    )
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0, stdout=inventory))

    pull_calls: list[list[str]] = []

    def _run_ok(argv: list[str], **_k: object) -> bool:
        pull_calls.append(list(argv))
        return True

    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, out = _ctx()

    ollama.install_ollama_models(ctx)

    assert "Ollama model qwen3:4b-instruct-2507-q4_K_M already present" in out.getvalue()
    assert "Ollama model qwen3-vl:4b-instruct already present" in out.getvalue()
    assert ["ollama", "pull", "qwen3:4b-instruct-2507-q4_K_M"] not in pull_calls
    assert ["ollama", "pull", "qwen3-vl:4b-instruct"] not in pull_calls


def test_pull_failure_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed `ollama pull` degrades to a warn (non-fatal)."""
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/local/bin/ollama")
    _patch_model_ids(monkeypatch)
    _patch_server_up(monkeypatch)
    _patch_mlx(monkeypatch, supported=False)
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0, stdout="HEADER\n"))
    monkeypatch.setattr(commands, "run_ok", lambda *_a, **_k: False)
    ctx, _ = _ctx()

    ollama.install_ollama_models(ctx)

    assert any("Ollama pull failed for qwen3:4b-instruct-2507-q4_K_M" in w for w in ctx.ui.warnings)
    assert any("Ollama pull failed for qwen3-vl:4b-instruct" in w for w in ctx.ui.warnings)


def test_list_failure_treated_as_empty_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    """A nonzero `ollama list` is treated as an empty inventory → the model is pulled."""
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/local/bin/ollama")
    _patch_model_ids(monkeypatch)
    _patch_server_up(monkeypatch)
    _patch_mlx(monkeypatch, supported=False)
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 1, stdout=""))

    pull_calls: list[list[str]] = []

    def _run_ok(argv: list[str], **_k: object) -> bool:
        pull_calls.append(list(argv))
        return True

    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, _ = _ctx()

    ollama.install_ollama_models(ctx)

    assert ["ollama", "pull", "qwen3:4b-instruct-2507-q4_K_M"] in pull_calls


def test_mlx_supported_pulls_all_four(monkeypatch: pytest.MonkeyPatch) -> None:
    """On a capable machine, all four role models are pulled."""
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/local/bin/ollama")
    _patch_model_ids(monkeypatch)
    _patch_server_up(monkeypatch)
    _patch_mlx(monkeypatch, supported=True)
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0, stdout="HEADER\n"))

    pull_calls: list[list[str]] = []

    def _run_ok(argv: list[str], **_k: object) -> bool:
        pull_calls.append(list(argv))
        return True

    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, _ = _ctx()

    ollama.install_ollama_models(ctx)

    assert ["ollama", "pull", "qwen3:4b-instruct-2507-q4_K_M"] in pull_calls
    assert ["ollama", "pull", "qwen3-vl:4b-instruct"] in pull_calls
    assert ["ollama", "pull", "qwen3.5:35b-a3b-coding-nvfp4"] in pull_calls
    assert ["ollama", "pull", "gemma4:26b"] in pull_calls


# --- _list_installed_models -------------------------------------------------------------------


def test_list_installed_models_drops_header_and_blanks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Column 1 of every non-blank line after the header is returned."""
    stdout = "NAME  ID\nfoo:1  a\n\nbar:2  b\n"
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0, stdout=stdout))

    assert ollama._list_installed_models() == ["foo:1", "bar:2"]


# --- _ensure_server_up ------------------------------------------------------------------------


def test_ensure_server_up_fast_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the first probe succeeds, no app launch / serve happens."""
    monkeypatch.setattr(ollama, "_server_responding", lambda: True)

    def _boom(*_a: object, **_k: object) -> object:
        msg = "no fallback should run on the fast path"
        raise AssertionError(msg)

    monkeypatch.setattr(commands, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    ctx, out = _ctx()

    ollama._ensure_server_up(ctx)

    assert "starting Ollama" not in out.getvalue()


def test_ensure_server_up_recovers_after_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Probe fails, the app is launched, the retry succeeds → no detached serve, no warn."""
    monkeypatch.setattr(ollama, "_server_responding", lambda: False)
    monkeypatch.setattr(ollama, "_server_responding_with_retry", lambda: True)

    run_calls: list[list[str]] = []
    monkeypatch.setattr(
        commands,
        "run",
        lambda argv, **_k: (run_calls.append(list(argv)), _completed(argv, 0))[1],
    )

    def _boom(*_a: object, **_k: object) -> object:
        msg = "serve should not start when the retry succeeds"
        raise AssertionError(msg)

    monkeypatch.setattr(subprocess, "Popen", _boom)
    ctx, out = _ctx()

    ollama._ensure_server_up(ctx)

    assert ["open", "-a", "Ollama"] in run_calls
    assert "starting Ollama" in out.getvalue()
    assert ctx.ui.warnings == []


def test_ensure_server_up_recovers_after_detached_serve(monkeypatch: pytest.MonkeyPatch) -> None:
    """App launch doesn't help, but the detached serve does → serve spawned, no warn."""
    monkeypatch.setattr(ollama, "_server_responding", lambda: False)
    # First retry (after open) fails; second retry (after serve) succeeds.
    retries = iter([False, True])
    monkeypatch.setattr(ollama, "_server_responding_with_retry", lambda: next(retries))
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0))

    popen_argvs: list[list[str]] = []

    def _popen(argv: list[str], **_k: object) -> object:
        popen_argvs.append(list(argv))
        return object()

    monkeypatch.setattr(subprocess, "Popen", _popen)
    ctx, _ = _ctx()

    ollama._ensure_server_up(ctx)

    assert popen_argvs == [["ollama", "serve"]]
    assert ctx.ui.warnings == []


def test_ensure_server_up_warns_when_still_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both retries fail after the detached serve → a warn is emitted."""
    monkeypatch.setattr(ollama, "_server_responding", lambda: False)
    monkeypatch.setattr(ollama, "_server_responding_with_retry", lambda: False)
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0))
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: object())
    ctx, _ = _ctx()

    ollama._ensure_server_up(ctx)

    assert any("Ollama server didn't come up" in w for w in ctx.ui.warnings)


def test_detached_serve_is_session_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    """The detached serve passes start_new_session=True and DEVNULL for stdout/stderr."""
    monkeypatch.setattr(ollama, "_server_responding", lambda: False)
    monkeypatch.setattr(ollama, "_server_responding_with_retry", lambda: False)
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0))

    captured: dict[str, object] = {}

    def _popen(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = list(argv)
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(subprocess, "Popen", _popen)
    ctx, _ = _ctx()

    ollama._ensure_server_up(ctx)

    assert captured["argv"] == ["ollama", "serve"]
    assert captured["start_new_session"] is True
    assert captured["stdout"] == subprocess.DEVNULL
    assert captured["stderr"] == subprocess.DEVNULL


# --- _mlx_supported ---------------------------------------------------------------------------


def test_mlx_gate_false_on_intel(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-arm64 machine fails the gate without consulting memory or macOS version."""
    monkeypatch.setattr(ollama.platform, "machine", lambda: "x86_64")

    def _boom() -> int:
        msg = "memory should not be probed on Intel"
        raise AssertionError(msg)

    monkeypatch.setattr(ollama, "_mem_bytes", _boom)

    assert ollama._mlx_supported() is False


def test_mlx_gate_false_at_exactly_32gib(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exactly 32 GiB fails the strictly-greater memory check."""
    monkeypatch.setattr(ollama.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(ollama, "_mem_bytes", lambda: ollama._MEM_32_GIB_BYTES)

    assert ollama._mlx_supported() is False


def test_mlx_gate_false_on_old_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enough RAM but macOS 12 fails the version check."""
    monkeypatch.setattr(ollama.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(ollama, "_mem_bytes", lambda: ollama._MEM_32_GIB_BYTES + 1)
    monkeypatch.setattr(ollama, "_macos_major", lambda: 12)

    assert ollama._mlx_supported() is False


def test_mlx_gate_true_when_all_met(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apple Silicon + >32 GiB + macOS 13 passes the gate (OS pinned for any test host)."""
    monkeypatch.setattr(ollama.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(ollama, "_mem_bytes", lambda: ollama._MEM_32_GIB_BYTES + 1)
    monkeypatch.setattr(ollama, "_macos_major", lambda: ollama._MIN_MACOS_MAJOR)

    assert ollama._mlx_supported() is True


def test_mlx_gate_false_off_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-macOS host fails the gate up front — no sysctl/sw_vers probes are consulted."""
    monkeypatch.setattr(ollama, "current_os", lambda: OS.LINUX)
    monkeypatch.setattr(ollama.platform, "machine", lambda: "arm64")  # even on Apple hardware

    def _boom() -> int:
        msg = "memory/version must not be probed off macOS"
        raise AssertionError(msg)

    monkeypatch.setattr(ollama, "_mem_bytes", _boom)
    monkeypatch.setattr(ollama, "_macos_major", _boom)

    assert ollama._mlx_supported() is False


# --- _mem_bytes / _macos_major ----------------------------------------------------------------


def test_mem_bytes_reads_sysctl(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sysctl output is parsed as an int."""
    expected = 68719476736  # 64 GiB
    out = f"{expected}\n"
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0, stdout=out))

    assert ollama._mem_bytes() == expected


def test_mem_bytes_zero_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A nonzero sysctl exit degrades to 0."""
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 1, stdout=""))

    assert ollama._mem_bytes() == 0


def test_mem_bytes_zero_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-numeric sysctl output degrades to 0."""
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0, stdout="nope"))

    assert ollama._mem_bytes() == 0


def test_macos_major_parses_first_component(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first dotted component of the product version is returned as an int."""
    expected = 14
    out = f"{expected}.5.1\n"
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0, stdout=out))

    assert ollama._macos_major() == expected


def test_macos_major_zero_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A nonzero sw_vers exit degrades to 0."""
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 1, stdout=""))

    assert ollama._macos_major() == 0


def test_macos_major_zero_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-numeric sw_vers output degrades to 0."""
    monkeypatch.setattr(commands, "run", lambda argv, **_k: _completed(argv, 0, stdout="beta\n"))

    assert ollama._macos_major() == 0


# --- _server_responding helpers ---------------------------------------------------------------


def test_server_responding_uses_short_curl(monkeypatch: pytest.MonkeyPatch) -> None:
    """The quick probe uses `curl -fsS -m 2` against the API url."""
    calls: list[list[str]] = []

    def _run_ok(argv: list[str], **_k: object) -> bool:
        calls.append(list(argv))
        return True

    monkeypatch.setattr(commands, "run_ok", _run_ok)

    assert ollama._server_responding() is True
    assert calls == [["curl", "-fsS", "-m", "2", ollama._API_URL]]


def test_server_responding_with_retry_uses_retry_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry probe passes --retry-connrefused and a 30s budget."""
    calls: list[list[str]] = []

    def _run_ok(argv: list[str], **_k: object) -> bool:
        calls.append(list(argv))
        return False

    monkeypatch.setattr(commands, "run_ok", _run_ok)

    assert ollama._server_responding_with_retry() is False
    assert calls[0] == [
        "curl",
        "-fsS",
        "--retry",
        "20",
        "--retry-delay",
        "1",
        "--retry-connrefused",
        "-m",
        "30",
        ollama._API_URL,
    ]
