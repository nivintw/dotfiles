# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Behavior tests for `home/.local/bin/ollm-tools-loop`, the sandboxed `--tools` engine.

Loaded by file path (its name has no `.py` suffix — it's a stowed CLI, not an importable
module) via `importlib.machinery.SourceFileLoader`. Network calls go through
`urllib.request.urlopen`, monkeypatched here so the loop logic is exercised without a real
Ollama server; the sandboxing tests (the security-critical half) need no network at all.
"""

from __future__ import annotations

import importlib.util
import json
from importlib.machinery import SourceFileLoader
from typing import TYPE_CHECKING

import pytest
from conftest import REPO

if TYPE_CHECKING:
    import urllib.request
    from pathlib import Path
    from types import ModuleType
    from typing import Self

SCRIPT = REPO / "home" / ".local" / "bin" / "ollm-tools-loop"

# capability probe (/api/show) + one /api/chat round, the shape of most happy-path fixtures
_CALLS_PROBE_PLUS_ONE_CHAT = 2


@pytest.fixture
def loop() -> ModuleType:
    """Load ollm-tools-loop as a module (it has no .py suffix, so import machinery is manual)."""
    loader = SourceFileLoader("ollm_tools_loop", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A root dir with a nested file, plus a sibling dir outside the root to escape to."""
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "f.txt").write_text("hello\nworld\n")
    (root / "empty").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("TOP SECRET\n")
    return root


# --- safe_path: the security-critical sandboxing property --------------------------------------


def test_safe_path_allows_a_normal_relative_path(loop: ModuleType, sandbox: Path) -> None:
    """A plain relative path under root resolves normally."""
    target = loop.safe_path(sandbox, "sub/f.txt")
    assert target == (sandbox / "sub" / "f.txt").resolve()


def test_safe_path_blocks_dotdot_traversal(loop: ModuleType, sandbox: Path) -> None:
    """A single ../ escape attempt is rejected."""
    with pytest.raises(loop.SandboxError):
        loop.safe_path(sandbox, "../outside/secret.txt")


def test_safe_path_blocks_deeply_nested_dotdot_traversal(loop: ModuleType, sandbox: Path) -> None:
    """Multiple ../ segments buried in a longer path are still caught after resolution."""
    with pytest.raises(loop.SandboxError):
        loop.safe_path(sandbox, "sub/../../outside/secret.txt")


def test_safe_path_neutralizes_absolute_paths_instead_of_escaping(
    loop: ModuleType, sandbox: Path
) -> None:
    """An absolute-looking path from the model is treated as root-relative, not literal.

    Otherwise Path.joinpath's own semantics (an absolute 2nd operand discards the 1st) would
    let a plain `/etc/passwd` argument walk straight out of the sandbox.
    """
    outside_secret = sandbox.parent / "outside" / "secret.txt"
    target = loop.safe_path(sandbox, str(outside_secret))
    assert str(target).startswith(str(sandbox))


def test_safe_path_blocks_symlink_escape(loop: ModuleType, sandbox: Path) -> None:
    """A symlink inside root pointing outside it is still caught (resolve() follows it first)."""
    (sandbox / "escape").symlink_to(sandbox.parent / "outside")
    with pytest.raises(loop.SandboxError):
        loop.safe_path(sandbox, "escape/secret.txt")


def test_safe_path_allows_the_root_itself(loop: ModuleType, sandbox: Path) -> None:
    """The current-directory path resolves to root itself, not a violation."""
    assert loop.safe_path(sandbox, ".") == sandbox.resolve()


@pytest.mark.parametrize("bad_path", [[1, 2, 3], 42, None, {}, ""], ids=str)
def test_safe_path_rejects_a_non_string_path_as_a_tool_error(
    loop: ModuleType, sandbox: Path, bad_path: object
) -> None:
    """A non-string (or empty) path is a ToolError here, not an AttributeError from .lstrip().

    This is the single choke point every tool (read_file/ls/grep) resolves paths
    through — found via Copilot review that ls and grep both lacked their own
    isinstance check that read_file already had, letting a non-string `path` argument
    crash the whole loop instead of producing a graceful tool-error result.
    """
    with pytest.raises(loop.ToolError):
        loop.safe_path(sandbox, bad_path)


# --- individual tools ----------------------------------------------------------------------


def test_read_file_returns_contents(loop: ModuleType, sandbox: Path) -> None:
    """read_file returns the file's text verbatim."""
    assert loop.tool_read_file(sandbox, {"path": "sub/f.txt"}) == "hello\nworld\n"


def test_read_file_missing_path_arg_is_a_tool_error(loop: ModuleType, sandbox: Path) -> None:
    """A missing 'path' argument is a ToolError, not an unhandled exception."""
    with pytest.raises(loop.ToolError):
        loop.tool_read_file(sandbox, {})


def test_read_file_on_a_directory_is_a_tool_error(loop: ModuleType, sandbox: Path) -> None:
    """Pointing read_file at a directory is a ToolError."""
    with pytest.raises(loop.ToolError):
        loop.tool_read_file(sandbox, {"path": "sub"})


def test_read_file_truncates_past_the_byte_cap(loop: ModuleType, sandbox: Path) -> None:
    """A file larger than MAX_READ_BYTES is truncated with a visible marker, not silently."""
    big = sandbox / "big.txt"
    big.write_text("x" * (loop.MAX_READ_BYTES + 100))
    result = loop.tool_read_file(sandbox, {"path": "big.txt"})
    assert "truncated" in result
    assert len(result) < loop.MAX_READ_BYTES + 100


def test_ls_lists_directory_entries(loop: ModuleType, sandbox: Path) -> None:
    """Ls lists both subdirectories at the root, marked as directories."""
    result = loop.tool_ls(sandbox, {"path": "."})
    assert "d sub" in result
    assert "d empty" in result


def test_ls_on_empty_directory(loop: ModuleType, sandbox: Path) -> None:
    """An empty directory reports itself as such rather than an empty string."""
    assert loop.tool_ls(sandbox, {"path": "empty"}) == "(empty directory)"


def test_ls_on_a_file_is_a_tool_error(loop: ModuleType, sandbox: Path) -> None:
    """Pointing ls at a file (not a directory) is a ToolError."""
    with pytest.raises(loop.ToolError):
        loop.tool_ls(sandbox, {"path": "sub/f.txt"})


def test_ls_rejects_a_non_string_path(loop: ModuleType, sandbox: Path) -> None:
    """A non-string path argument is a ToolError, not an AttributeError crash."""
    with pytest.raises(loop.ToolError):
        loop.tool_ls(sandbox, {"path": [1, 2, 3]})


def test_grep_finds_matches_with_file_and_line(loop: ModuleType, sandbox: Path) -> None:
    """A match is reported as relative-path:line-number:line-text."""
    result = loop.tool_grep(sandbox, {"pattern": "wor.d", "path": "."})
    assert result == "sub/f.txt:2:world"


def test_grep_no_matches(loop: ModuleType, sandbox: Path) -> None:
    """No matches reports a clear placeholder rather than an empty string."""
    assert loop.tool_grep(sandbox, {"pattern": "nope-not-here", "path": "."}) == "(no matches)"


def test_grep_invalid_regex_is_a_tool_error(loop: ModuleType, sandbox: Path) -> None:
    """An unparsable regex is a ToolError, not an unhandled re.error."""
    with pytest.raises(loop.ToolError):
        loop.tool_grep(sandbox, {"pattern": "(unclosed", "path": "."})


def test_grep_rejects_a_non_string_path(loop: ModuleType, sandbox: Path) -> None:
    """A non-string path argument is a ToolError, not an AttributeError crash."""
    with pytest.raises(loop.ToolError):
        loop.tool_grep(sandbox, {"pattern": "x", "path": [1, 2, 3]})


def test_grep_skips_binary_files(loop: ModuleType, sandbox: Path) -> None:
    """A file with a NUL byte in its first chunk is skipped as binary."""
    (sandbox / "bin.dat").write_bytes(b"\x00\x01wor\x00ld")
    result = loop.tool_grep(sandbox, {"pattern": "wor", "path": "."})
    assert "bin.dat" not in result


def test_grep_skips_dot_git(loop: ModuleType, sandbox: Path) -> None:
    """.git internals are never scanned, even if they'd otherwise match."""
    (sandbox / ".git").mkdir()
    (sandbox / ".git" / "config").write_text("world\n")
    result = loop.tool_grep(sandbox, {"pattern": "world", "path": "."})
    assert ".git" not in result


def test_grep_does_not_follow_a_symlinked_file_out_of_the_sandbox(
    loop: ModuleType, sandbox: Path
) -> None:
    """A symlink inside root pointing at a file outside it is not read by grep.

    tool_read_file/tool_ls already defeat this via safe_path on their single path
    argument; grep walks a whole tree, so each file it visits needs the same check.
    """
    (sandbox / "link.txt").symlink_to(sandbox.parent / "outside" / "secret.txt")
    result = loop.tool_grep(sandbox, {"pattern": "TOP SECRET", "path": "."})
    assert "TOP SECRET" not in result


def test_grep_still_matches_a_symlink_pointing_back_inside_the_sandbox(
    loop: ModuleType, sandbox: Path
) -> None:
    """A symlink that happens to resolve back inside root is not penalized as an escape."""
    (sandbox / "link_inside.txt").symlink_to(sandbox / "sub" / "f.txt")
    result = loop.tool_grep(sandbox, {"pattern": "world", "path": "."})
    assert "link_inside.txt" in result


def test_grep_on_a_nonexistent_path_does_not_raise(loop: ModuleType, sandbox: Path) -> None:
    """A grep path that doesn't exist reports no matches rather than crashing on scandir."""
    assert loop.tool_grep(sandbox, {"pattern": "x", "path": "does/not/exist"}) == "(no matches)"


def test_grep_skips_a_self_referential_symlink_without_raising(
    loop: ModuleType, sandbox: Path
) -> None:
    """A symlink pointing at itself (ELOOP) is skipped, not an unhandled OSError."""
    (sandbox / "selfloop").symlink_to(sandbox / "selfloop")
    result = loop.tool_grep(sandbox, {"pattern": "world", "path": "."})
    assert "sub/f.txt:2:world" in result  # the walk continues past the bad entry


def test_grep_caps_bytes_read_per_file(loop: ModuleType, sandbox: Path) -> None:
    """A file larger than MAX_READ_BYTES is only scanned up to that cap, not read whole."""
    big = sandbox / "big.txt"
    filler = "x" * (loop.MAX_READ_BYTES + 1000)
    big.write_text(filler + "\nneedle-past-the-cap\n")
    result = loop.tool_grep(sandbox, {"pattern": "needle-past-the-cap", "path": "big.txt"})
    assert result == "(no matches)"  # the match lives past MAX_READ_BYTES, never read


def test_grep_regex_timeout_is_bounded_and_reported(
    loop: ModuleType, sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A catastrophic-backtracking pattern is cut off, not left to hang the process.

    Uses a real catastrophic pattern ((a|aa)+b against a run of 'a's with no trailing
    'b') so this actually exercises the regex package's own timeout mechanism, not a
    mock — with the timeout shortened so the test itself stays fast.
    """
    monkeypatch.setattr(loop, "GREP_LINE_TIMEOUT_SECONDS", 0.2)
    (sandbox / "bad.txt").write_text("a" * 40 + "!\n")
    result = loop.tool_grep(sandbox, {"pattern": "(a|aa)+b", "path": "bad.txt"})
    assert "stopped" in result
    assert "catastrophic" in result


def test_ls_caps_entries(loop: ModuleType, sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A directory with more entries than the cap is truncated with a visible marker."""
    monkeypatch.setattr(loop, "MAX_LS_ENTRIES", 2)
    many = sandbox / "many"
    many.mkdir()
    entry_count = 5
    for i in range(entry_count):
        (many / f"f{i}").write_text("x")
    result = loop.tool_ls(sandbox, {"path": "many"})
    lines = result.splitlines()
    assert len(lines) == loop.MAX_LS_ENTRIES + 1  # the capped entries plus the marker line
    assert "stopped after 2 entries" in lines[-1]


# --- run_tool dispatch: errors become tool results, never exceptions ------------------------


def test_run_tool_unknown_name_returns_an_error_string(loop: ModuleType, sandbox: Path) -> None:
    """An unrecognized tool name is reported back to the model, not raised."""
    result = loop.run_tool(sandbox, "delete_everything", {})
    assert result.startswith("error:")


def test_run_tool_non_string_name_does_not_raise(loop: ModuleType, sandbox: Path) -> None:
    """An unhashable tool name is coerced to an error, not a raised TypeError.

    A list/dict tool name would otherwise raise TypeError from DISPATCH.get() trying
    to hash it — found via Copilot review.
    """
    result = loop.run_tool(sandbox, [1, 2], {})
    assert result.startswith("error:")


def test_run_tool_sandbox_violation_returns_an_error_string(
    loop: ModuleType, sandbox: Path
) -> None:
    """A sandbox escape attempt is reported back to the model, not raised out of the loop."""
    result = loop.run_tool(sandbox, "read_file", {"path": "../outside/secret.txt"})
    assert result.startswith("error:")


def test_run_tool_non_dict_args_does_not_raise(loop: ModuleType, sandbox: Path) -> None:
    """A tool-call args shape violation is coerced, not left to crash with AttributeError.

    Tool-call arguments can arrive as a non-dict (a model/server shape violation); run_tool
    must coerce rather than crash on the first `.get()` call inside the tool implementation.
    """
    result = loop.run_tool(sandbox, "read_file", [1, 2, 3])
    assert result.startswith("error:")


def test_run_tool_null_byte_in_path_does_not_raise(loop: ModuleType, sandbox: Path) -> None:
    """A NUL byte in a path is reported like any other bad path, not left to crash.

    Path.resolve() raises a plain ValueError for a NUL byte internally — caught here like
    any other bad-path failure, not left to escape run_tool and kill the whole process.
    """
    result = loop.run_tool(sandbox, "read_file", {"path": "foo\x00bar"})
    assert result.startswith("error:")


# --- main(): the chat loop, with urlopen stubbed --------------------------------------------


class _FakeResponse:
    """Stands in for the context-managed object urllib.request.urlopen() returns."""

    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _stub_urlopen(responses: list[dict]) -> tuple[list[dict], object]:
    """Build a fake urlopen serving one canned response per call, in order.

    Returns (calls, urlopen_fn): calls collects each request's decoded JSON body as it's made.
    """
    calls: list[dict] = []
    queue = list(responses)

    def fake_urlopen(
        req: urllib.request.Request,
        timeout: float | None = None,  # noqa: ARG001
    ) -> _FakeResponse:
        calls.append(json.loads(req.data))
        return _FakeResponse(queue.pop(0))

    return calls, fake_urlopen


def _argv(sandbox: Path, *extra: str) -> list[str]:
    """Build a base sys.argv for ollm-tools-loop, with extra flags/prompt appended."""
    return [
        "ollm-tools-loop",
        "--url",
        "http://fake",
        "--model",
        "m",
        "--timeout",
        "5",
        "--num-predict",
        "100",
        "--root",
        str(sandbox),
        *extra,
    ]


def test_main_happy_path_no_tool_calls(
    loop: ModuleType,
    sandbox: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """A model that answers immediately, with no tool calls, prints its text and exits 0."""
    calls, fake_urlopen = _stub_urlopen(
        [
            {"capabilities": ["tools"]},  # /api/show
            {"message": {"role": "assistant", "content": "hello world"}},  # /api/chat
        ]
    )
    monkeypatch.setattr(loop.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("sys.argv", _argv(sandbox, "hi"))
    loop.main()
    assert capsys.readouterr().out == "hello world\n"
    assert len(calls) == _CALLS_PROBE_PLUS_ONE_CHAT


def test_main_model_without_tools_capability_dies(
    loop: ModuleType, sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model that doesn't advertise tool-calling fails fast instead of silently misbehaving."""
    _calls, fake_urlopen = _stub_urlopen([{"capabilities": []}])
    monkeypatch.setattr(loop.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("sys.argv", _argv(sandbox, "hi"))
    with pytest.raises(SystemExit) as exc:
        loop.main()
    assert exc.value.code == 1


def test_main_runs_a_tool_call_then_returns_final_answer(
    loop: ModuleType,
    sandbox: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """A tool call is executed and its result fed back before the model's final answer."""
    tool_call_message = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "sub/f.txt"}}}],
    }
    calls, fake_urlopen = _stub_urlopen(
        [
            {"capabilities": ["tools"]},
            {"message": tool_call_message},
            {"message": {"role": "assistant", "content": "the file says hello world"}},
        ]
    )
    monkeypatch.setattr(loop.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("sys.argv", _argv(sandbox, "what does the file say?"))
    loop.main()
    assert capsys.readouterr().out == "the file says hello world\n"
    # third call (second /api/chat) must carry the tool result in its message history
    last_messages = calls[2]["messages"]
    assert any(m.get("role") == "tool" and "hello" in m.get("content", "") for m in last_messages)


@pytest.mark.parametrize(
    "bad_message",
    [{"role": "assistant", "content": "", "tool_calls": {"not": "a list"}}, "a bare string"],
    ids=["tool_calls-as-dict", "message-as-string"],
)
def test_main_treats_a_shapeless_message_as_an_empty_response_not_a_crash(
    loop: ModuleType,
    sandbox: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_message: object,
) -> None:
    """A message with no usable content AND no usable tool_calls dies cleanly.

    Once `tool_calls` and `content` both coerce to empty, this is legitimately the
    existing empty-response guard's job (matching a real model that returned nothing) —
    the fix is that it's a controlled die(), never an uncaught AttributeError/TypeError.
    """
    _calls, fake_urlopen = _stub_urlopen([{"capabilities": ["tools"]}, {"message": bad_message}])
    monkeypatch.setattr(loop.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("sys.argv", _argv(sandbox, "hi"))
    with pytest.raises(SystemExit) as exc:
        loop.main()
    assert exc.value.code == 1


@pytest.mark.parametrize(
    "bad_tool_calls",
    [
        [{"function": ["not", "a", "dict"]}],
        ["not a dict call"],
    ],
    ids=["function-not-a-dict", "call-not-a-dict"],
)
def test_main_recovers_from_a_malformed_individual_tool_call(
    loop: ModuleType,
    sandbox: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    bad_tool_calls: list,
) -> None:
    """A malformed entry keeps the loop going instead of crashing.

    An otherwise-normal tool_calls list with one malformed entry gets an error tool
    result for that entry, and the loop continues to the next round.
    """
    bad_message = {"role": "assistant", "content": "", "tool_calls": bad_tool_calls}
    calls, fake_urlopen = _stub_urlopen(
        [
            {"capabilities": ["tools"]},
            {"message": bad_message},
            {"message": {"role": "assistant", "content": "recovered"}},
        ]
    )
    monkeypatch.setattr(loop.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("sys.argv", _argv(sandbox, "hi"))
    loop.main()
    assert capsys.readouterr().out == "recovered\n"
    last_messages = calls[2]["messages"]
    assert any(m.get("role") == "tool" and "error" in m.get("content", "") for m in last_messages)


def test_main_sends_explicit_think_false_for_a_thinking_capable_model(
    loop: ModuleType, sandbox: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A model that supports both tools and thinking gets an explicit think:false.

    Mirrors ollm's own non-tools path: hidden thinking otherwise eats the token budget and
    yields an empty response, which is exactly the footgun --think exists to opt out of.
    """
    calls, fake_urlopen = _stub_urlopen(
        [
            {"capabilities": ["tools", "thinking"]},
            {"message": {"role": "assistant", "content": "hello world"}},
        ]
    )
    monkeypatch.setattr(loop.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("sys.argv", _argv(sandbox, "hi"))
    loop.main()
    assert capsys.readouterr().out == "hello world\n"
    assert calls[1]["think"] is False


def test_main_gives_up_after_cap_rounds_of_tool_calls(
    loop: ModuleType, sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model that never stops calling tools is cut off at --cap rather than looping forever."""
    tool_call_message = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "ls", "arguments": {"path": "."}}}],
    }
    cap = 2
    responses = [{"capabilities": ["tools"]}, *([{"message": tool_call_message}] * cap)]
    _calls, fake_urlopen = _stub_urlopen(responses)
    monkeypatch.setattr(loop.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("sys.argv", _argv(sandbox, "--cap", str(cap), "loop forever"))
    with pytest.raises(SystemExit) as exc:
        loop.main()
    assert exc.value.code == 1


def test_main_empty_response_with_done_reason_length_blames_token_budget(
    loop: ModuleType, sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty final message with done_reason=length names the token budget, like ollm itself."""
    calls, fake_urlopen = _stub_urlopen(
        [
            {"capabilities": ["tools"]},
            {"message": {"role": "assistant", "content": ""}, "done_reason": "length"},
        ]
    )
    monkeypatch.setattr(loop.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("sys.argv", _argv(sandbox, "hi"))
    with pytest.raises(SystemExit) as exc:
        loop.main()
    assert exc.value.code == 1
    assert len(calls) == _CALLS_PROBE_PLUS_ONE_CHAT


def test_main_think_requested_but_unsupported_dies(
    loop: ModuleType, sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--think on a model without the thinking capability fails, mirroring ollm's own check."""
    _calls, fake_urlopen = _stub_urlopen([{"capabilities": ["tools"]}])
    monkeypatch.setattr(loop.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("sys.argv", _argv(sandbox, "--think", "hi"))
    with pytest.raises(SystemExit) as exc:
        loop.main()
    assert exc.value.code == 1


def test_main_rejects_a_non_directory_root(
    loop: ModuleType, sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--root pointing at a file (not a directory) is rejected before any network call."""
    bad_root = sandbox / "sub" / "f.txt"
    monkeypatch.setattr("sys.argv", _argv(bad_root, "hi"))
    with pytest.raises(SystemExit) as exc:
        loop.main()
    assert exc.value.code == 1


def test_main_rejects_a_non_positive_cap(
    loop: ModuleType, sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--cap 0 is rejected before any network call."""
    monkeypatch.setattr("sys.argv", _argv(sandbox, "--cap", "0", "hi"))
    with pytest.raises(SystemExit) as exc:
        loop.main()
    assert exc.value.code == 1
