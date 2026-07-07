<!-- Shared install snippet, included via pymdownx.snippets (`--8<-- "install.md"`) from any
     docs page that needs the quick-start, so the instructions can't drift between copies
     (nivintw/repo-management#96).

     No inline SPDX header: this repo is frontmatter-first, so markdown is licensed via
     REUSE.toml's `**/*.md` annotation (see .config/licenserc.toml) — and this fragment is
     spliced INTO other pages, where a header comment would be duplicated inline. -->

No toolchain to install first — `install.sh` bootstraps Homebrew and uv itself.

```bash
git clone https://github.com/nivintw/dotfiles ~/dotfiles
~/dotfiles/install.sh
```

Runs the same way on **macOS, Linux, and WSL2** — the macOS-only phases skip themselves
elsewhere. It's idempotent: re-run it any time and it converges the machine to the declared
state instead of clobbering it.
